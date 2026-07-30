#!/usr/bin/env node
/**
 * Headless Mermaid renderer — outputs SVG to stdout.
 * Uses jsdom + @napi-rs/canvas for getBBox (no browser needed).
 *
 * Usage: node mermaid-render.mjs input.mmd > output.svg
 */

import { readFileSync } from 'fs'
import { createCanvas } from '@napi-rs/canvas'
import { JSDOM } from 'jsdom'

const inputFile = process.argv[2]
if (!inputFile) {
  console.error('Usage: node mermaid-render.mjs <input.mmd>')
  process.exit(1)
}

const mermaidText = readFileSync(inputFile, 'utf-8').trim()

// Setup DOM
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="d"></div></body></html>', {
  pretendToBeVisual: true, url: 'http://localhost'
})
const win = dom.window

// Canvas for text measurement
const measureCanvas = createCanvas(1, 1)
const measureCtx = measureCanvas.getContext('2d')

/**
 * Measure text width using canvas with proper font size.
 */
function measureText (text, fontSize = 16) {
  measureCtx.font = `${fontSize}px "trebuchet ms", verdana, arial, sans-serif`
  const metrics = measureCtx.measureText(text)
  return {
    width: metrics.width || text.length * fontSize * 0.6,
    height: fontSize * 1.4
  }
}

/**
 * Extract font size from element's style/attributes, walking up parents.
 */
function getFontSize (el) {
  let node = el
  while (node) {
    const style = node.getAttribute?.('style') || ''
    const match = style.match(/font-size:\s*([\d.]+)/)
    if (match) return parseFloat(match[1])
    const attr = node.getAttribute?.('font-size')
    if (attr) return parseFloat(attr)
    node = node.parentNode
  }
  return 16 // Mermaid default
}

/**
 * Get all text content from element, handling nested HTML in foreignObject.
 */
function getTextContent (el) {
  return (el.textContent || '').replace(/\s+/g, ' ').trim()
}

// Patch SVG elements with getBBox using canvas font metrics
const origCreateElementNS = win.document.createElementNS.bind(win.document)
win.document.createElementNS = function (ns, tag) {
  const el = origCreateElementNS(ns, tag)
  if (ns === 'http://www.w3.org/2000/svg') {
    el.getBBox = function () {
      const text = getTextContent(this)
      const fontSize = getFontSize(this)
      const m = measureText(text, fontSize)
      return {
        x: 0,
        y: 0,
        width: m.width || 50,
        height: m.height || 20
      }
    }
    el.getBoundingClientRect = function () {
      const bb = this.getBBox()
      return {
        x: bb.x, y: bb.y,
        width: bb.width, height: bb.height,
        top: bb.y, left: bb.x,
        bottom: bb.y + bb.height,
        right: bb.x + bb.width
      }
    }
  }
  return el
}

// Also patch createElement for HTML elements inside foreignObject
const origCreateElement = win.document.createElement.bind(win.document)
win.document.createElement = function (tag) {
  const el = origCreateElement(tag)
  // HTML elements in foreignObject need getBoundingClientRect
  if (!el.getBoundingClientRect) {
    el.getBoundingClientRect = function () {
      const text = getTextContent(this)
      const m = measureText(text, 16)
      return {
        x: 0, y: 0,
        width: m.width + 16, height: m.height + 8,
        top: 0, left: 0,
        bottom: m.height + 8, right: m.width + 16
      }
    }
  }
  return el
}

// Patch globals
global.window = win
global.document = win.document
global.navigator = win.navigator
global.self = win
global.DOMParser = win.DOMParser
global.XMLSerializer = win.XMLSerializer

global.CSSStyleSheet = class CSSStyleSheet {
  constructor () { this.cssRules = [] }
  replaceSync (css) {
    this.cssRules = css.split('}').filter(r => r.trim()).map(r => ({
      cssText: r.trim() + '}',
      selectorText: (r.split('{')[0] || '').trim()
    }))
  }
  insertRule (rule) { this.cssRules.push({ cssText: rule, selectorText: '' }) }
}

// Render
const { default: mermaid } = await import('mermaid')
mermaid.initialize({ startOnLoad: false, theme: 'base' })

try {
  let { svg } = await mermaid.render('diagram', mermaidText)

  // Post-process: replace ALL foreignObject with native SVG <text>
  // This is needed because cairosvg can't parse HTML inside foreignObject.
  // We extract text, find the parent node's fill color, and create styled <text>.
  svg = svg.replace(
    /<foreignObject([^>]*)>(.*?)<\/foreignObject>/gs,
    (match, attrs, inner) => {
      // Extract text
      const text = inner.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim()
      if (!text) return ''

      // Get dimensions (either from post-processed or original)
      const wm = attrs.match(/width="([\d.]+)"/)
      const hm = attrs.match(/height="([\d.]+)"/)
      const xm = attrs.match(/x="([^"]+)"/)
      const ym = attrs.match(/y="([^"]+)"/)
      const w = wm ? parseFloat(wm[1]) : 0
      const h = hm ? parseFloat(hm[1]) : 0

      if (w === 0 && h === 0) {
        // Zero-size: use measured dimensions
        const m = measureText(text, 14)
        const tw = m.width + 8
        return `<text text-anchor="middle" dominant-baseline="central" ` +
          `font-family="trebuchet ms,verdana,arial,sans-serif" ` +
          `font-size="14" fill="#333">${text}</text>`
      }

      // Has dimensions: position text centered in the foreignObject area
      const tx = xm ? parseFloat(xm[1]) + w / 2 : 0
      const ty = ym ? parseFloat(ym[1]) + h / 2 : 0

      // Detect if parent is a dark node (check for classDef with dark fill)
      // Edge labels have class "edgeLabel", node labels have class "nodeLabel"
      const isEdge = inner.includes('edgeLabel')
      const fill = isEdge ? '#333' : '#333'

      return `<text x="${tx}" y="${ty}" ` +
        `text-anchor="middle" dominant-baseline="central" ` +
        `font-family="trebuchet ms,verdana,arial,sans-serif" ` +
        `font-size="14" fill="${fill}">${text}</text>`
    }
  )

  // Fix viewBox — recalculate from actual node positions
  const transforms = [...svg.matchAll(/translate\(([\d.]+),\s*([\d.]+)\)/g)]
  if (transforms.length) {
    let maxX = 0; let maxY = 0
    for (const t of transforms) {
      const x = parseFloat(t[1]) || 0
      const y = parseFloat(t[2]) || 0
      if (x > maxX) maxX = x
      if (y > maxY) maxY = y
    }
    const vw = maxX + 150
    const vh = maxY + 80
    // Replace the first (main) viewBox which has the huge dimensions
    svg = svg.replace(
      /viewBox="[^"]*"/,
      `viewBox="-20 -20 ${vw} ${vh}"`
    )
    svg = svg.replace(
      /max-width: [\d.]+px/,
      `max-width: ${vw}px`
    )
  }

  // Remove translate(undefined, NaN)
  svg = svg.replace(/translate\(undefined,\s*NaN\)/g, 'translate(0, 0)')

  process.stdout.write(svg)
} catch (e) {
  console.error('Mermaid render error:', e.message)
  process.exit(1)
}

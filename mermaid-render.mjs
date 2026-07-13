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

// Patch SVG elements with getBBox using canvas font metrics
const origCreateElementNS = win.document.createElementNS.bind(win.document)
win.document.createElementNS = function (ns, tag) {
  const el = origCreateElementNS(ns, tag)
  if (ns === 'http://www.w3.org/2000/svg') {
    el.getBBox = function () {
      const text = this.textContent || ''
      measureCtx.font = '14px sans-serif'
      const m = measureCtx.measureText(text)
      return { x: 0, y: 0, width: m.width || 50, height: 20 }
    }
    el.getBoundingClientRect = function () {
      const bb = this.getBBox()
      return { ...bb, top: 0, left: 0, bottom: bb.height, right: bb.width }
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
  const { svg } = await mermaid.render('diagram', mermaidText)
  process.stdout.write(svg)
} catch (e) {
  console.error('Mermaid render error:', e.message)
  process.exit(1)
}

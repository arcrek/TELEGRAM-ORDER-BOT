// Mirror-div caret coordinate measurement (standard textarea-caret technique).
const MIRROR_PROPS = [
  'boxSizing', 'width', 'height', 'overflowX', 'overflowY',
  'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'fontStyle', 'fontVariant', 'fontWeight', 'fontStretch', 'fontSize',
  'lineHeight', 'fontFamily', 'textAlign', 'textTransform', 'textIndent',
  'letterSpacing', 'wordSpacing', 'tabSize', 'whiteSpace', 'wordWrap',
] as const

export interface CaretCoords {
  top: number
  left: number
  height: number
}

export function getCaretCoordinates(el: HTMLTextAreaElement, position: number): CaretCoords {
  const doc = el.ownerDocument
  const computed = window.getComputedStyle(el)
  const div = doc.createElement('div')

  const style = div.style
  style.position = 'absolute'
  style.visibility = 'hidden'
  style.whiteSpace = 'pre-wrap'
  style.wordWrap = 'break-word'
  style.overflow = 'hidden'
  const styleMap = style as unknown as Record<string, string>
  const computedMap = computed as unknown as Record<string, string>
  for (const prop of MIRROR_PROPS) {
    styleMap[prop] = computedMap[prop]
  }

  doc.body.appendChild(div)
  try {
    div.textContent = el.value.slice(0, position)
    const span = doc.createElement('span')
    // A non-empty span gives a measurable box even at end-of-text.
    span.textContent = el.value.slice(position) || '.'
    div.appendChild(span)

    return {
      top: span.offsetTop,
      left: span.offsetLeft,
      height: parseInt(computed.lineHeight, 10) || el.offsetHeight,
    }
  } finally {
    doc.body.removeChild(div)
  }
}

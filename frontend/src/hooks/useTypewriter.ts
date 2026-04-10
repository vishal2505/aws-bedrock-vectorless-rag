import { useState, useEffect } from 'react'

/**
 * Progressively reveals text character-by-character, like a real AI typing.
 * When `text` changes the animation resets automatically.
 */
export function useTypewriter(text: string, speed = 12): string {
  const [displayed, setDisplayed] = useState('')

  useEffect(() => {
    if (!text) { setDisplayed(''); return }
    setDisplayed('')
    let i = 0
    const timer = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) clearInterval(timer)
    }, speed)
    return () => clearInterval(timer)
  }, [text, speed])

  return displayed
}

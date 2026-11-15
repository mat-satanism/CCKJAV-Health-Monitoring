// Two looks for the same app: "space" (the original dark console) and "paper" (light, WCAG 2.2 AA).
// Each theme is a whole stylesheet, loaded as text and swapped in one <style> tag, so neither changes the other.
// The choice is remembered in this browser only.
import paper from './themes/paper.css?inline'
import space from './themes/space.css?inline'

export type Theme = 'space' | 'paper'
const KEY = 'chn-theme'
const CSS: Record<Theme, string> = { space, paper }
const BAR: Record<Theme, string> = { space: '#05070f', paper: '#FFFFFF' }

export function savedTheme(): Theme {
  try { return localStorage.getItem(KEY) === 'paper' ? 'paper' : 'space' } catch { return 'space' }
}

export function applyTheme(theme: Theme): void {
  let tag = document.getElementById('theme-css') as HTMLStyleElement | null
  if (!tag) {
    tag = document.createElement('style')
    tag.id = 'theme-css'
    document.head.appendChild(tag)
  }
  tag.textContent = CSS[theme]
  document.documentElement.dataset.theme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BAR[theme])
  try { localStorage.setItem(KEY, theme) } catch { /* private mode: the choice just isn't remembered */ }
}

/* eslint-disable */
/**
 * Notification Sound - простий звук сповіщення через Web Audio API
 * Не потребує зовнішніх аудіо файлів
 */

// Створюємо AudioContext лише один раз
let audioContext = null

function getAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
  }
  return audioContext
}

/**
 * Відтворити звук сповіщення (короткий "дзінь")
 * @param {string} type - тип звуку: 'update' | 'join' | 'alert'
 */
export function playNotificationSound(type = 'update') {
  try {
    const ctx = getAudioContext()
    
    // Якщо контекст заблокований (autoplay policy) - спробувати розблокувати
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    
    const oscillator = ctx.createOscillator()
    const gainNode = ctx.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(ctx.destination)
    
    // Різні звуки для різних подій
    switch (type) {
      case 'update':
        // Приємний "дзінь" - два тони
        oscillator.frequency.setValueAtTime(880, ctx.currentTime) // A5
        oscillator.frequency.setValueAtTime(1100, ctx.currentTime + 0.1) // C#6
        gainNode.gain.setValueAtTime(0.15, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
        oscillator.start(ctx.currentTime)
        oscillator.stop(ctx.currentTime + 0.3)
        break
        
      case 'join':
        // Короткий "поп" - хтось приєднався
        oscillator.frequency.setValueAtTime(660, ctx.currentTime) // E5
        gainNode.gain.setValueAtTime(0.1, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15)
        oscillator.start(ctx.currentTime)
        oscillator.stop(ctx.currentTime + 0.15)
        break
        
      case 'alert':
        // Подвійний "біп" - важливе сповіщення
        oscillator.frequency.setValueAtTime(800, ctx.currentTime)
        oscillator.frequency.setValueAtTime(600, ctx.currentTime + 0.1)
        oscillator.frequency.setValueAtTime(800, ctx.currentTime + 0.2)
        gainNode.gain.setValueAtTime(0.2, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4)
        oscillator.start(ctx.currentTime)
        oscillator.stop(ctx.currentTime + 0.4)
        break
        
      case 'conflict':
        // Тривожний звук - конфлікт версій
        oscillator.type = 'square'
        oscillator.frequency.setValueAtTime(440, ctx.currentTime)
        oscillator.frequency.setValueAtTime(330, ctx.currentTime + 0.15)
        gainNode.gain.setValueAtTime(0.15, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
        oscillator.start(ctx.currentTime)
        oscillator.stop(ctx.currentTime + 0.3)
        break
        
      default:
        oscillator.frequency.setValueAtTime(800, ctx.currentTime)
        gainNode.gain.setValueAtTime(0.1, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2)
        oscillator.start(ctx.currentTime)
        oscillator.stop(ctx.currentTime + 0.2)
    }
    
  } catch (e) {
    // Тихо ігноруємо помилки (старі браузери або заблокований звук)
    console.log('[Sound] Unable to play notification:', e.message)
  }
}

/**
 * Перевірити чи звук дозволений
 */
export function isSoundEnabled() {
  try {
    const stored = localStorage.getItem('notification_sound')
    return stored !== 'disabled'
  } catch {
    return true
  }
}

/**
 * Увімкнути/вимкнути звук
 */
export function toggleSound(enabled) {
  try {
    localStorage.setItem('notification_sound', enabled ? 'enabled' : 'disabled')
  } catch {}
}

/**
 * Відтворити звук якщо він увімкнений
 */
export function playIfEnabled(type = 'update') {
  if (isSoundEnabled()) {
    playNotificationSound(type)
  }
}

export default playNotificationSound

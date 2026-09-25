import { useEffect, useState } from 'react'

import '../styles/first-task-toast.css'
import { FIRST_TASK_EVENT } from '../utils/firstCelebration.mjs'

// A tiny floating companion note for the first task of the day. Deliberately
// not a card, dialog, or toast-with-actions: pointer-events are off, it
// announces politely, and it dismisses itself after a few seconds.
export default function FirstTaskToast() {
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let timer = 0
    const show = () => {
      setNonce((value) => value + 1)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setNonce(0), 3600)
    }
    window.addEventListener(FIRST_TASK_EVENT, show)
    return () => {
      window.removeEventListener(FIRST_TASK_EVENT, show)
      window.clearTimeout(timer)
    }
  }, [])

  if (nonce === 0) return null
  return (
    <p key={nonce} className="first-task-toast" role="status">
      Good start. 🌱
    </p>
  )
}

import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
export interface ModalProps { isOpen: boolean; onClose: () => void; title: string; children: ReactNode; maxWidth?: string }
export function Modal({ isOpen, onClose, title, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = ref.current
    if (!isOpen || !dialog) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => { dialog.close(); document.body.style.overflow = overflow; previous?.focus() }
  }, [isOpen])
  return <dialog ref={ref} className="modal" aria-labelledby={titleId} onCancel={onClose} onClick={e => { if (e.target === ref.current) onClose() }}>
    {isOpen && <><div className="modal-header"><div><span className="eyebrow">DOCTUS WORKSPACE</span><h2 id={titleId}>{title}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button></div><div className="modal-body">{children}</div></>}
  </dialog>
}

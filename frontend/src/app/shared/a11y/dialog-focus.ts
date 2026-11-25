/**
 * Utilitários puros de acessibilidade para diálogos/painéis laterais:
 * seletor de focáveis, armadilha de foco (Tab/Shift+Tab) e trava de rolagem do body.
 * Extraído do price-equilibrium-drawer (F6) sem mudança de comportamento (Design Plan F7 Q-D4).
 */

export const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Mantém o foco circulando dentro do contêiner quando a tecla é Tab.
 */
export function trapFocus(event: KeyboardEvent, container: HTMLElement, doc: Document): void {
  const focusables = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  if (focusables.length === 0) return;

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active = doc.activeElement;

  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

/**
 * Trava a rolagem do body e devolve a função que restaura o valor anterior.
 */
export function lockBodyScroll(doc: Document): () => void {
  const previous = doc.body.style.overflow;
  doc.body.style.overflow = 'hidden';
  return () => {
    doc.body.style.overflow = previous;
  };
}

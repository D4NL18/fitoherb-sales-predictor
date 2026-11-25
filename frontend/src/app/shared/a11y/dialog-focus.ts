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

  // Foco fora do diálogo (ex.: clique em área não focável e Tab): traz de volta para dentro.
  if (!active || !container.contains(active)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return;
  }

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

/**
 * Torna `inert` tudo que está fora do diálogo: os irmãos de `container` e de cada ancestral até o body
 * (navbar, `main`, conteúdo da página). Devolve a função que restaura, sem remover o que já era `inert`.
 */
export function inertOutside(container: HTMLElement, doc: Document): () => void {
  const changed: Element[] = [];
  let node: Element | null = container;
  while (node && node !== doc.body) {
    const parent: Element | null = node.parentElement;
    if (!parent) break;
    for (const sibling of Array.from(parent.children)) {
      if (sibling !== node && !sibling.hasAttribute('inert')) {
        sibling.setAttribute('inert', '');
        changed.push(sibling);
      }
    }
    node = parent;
  }
  return () => changed.forEach((el) => el.removeAttribute('inert'));
}

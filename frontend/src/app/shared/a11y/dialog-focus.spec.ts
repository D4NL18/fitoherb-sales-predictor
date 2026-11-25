/**
 * Testes das funções puras de foco de diálogos (Design Plan F7 Q-D4).
 */
import { FOCUSABLE_SELECTOR, inertOutside, lockBodyScroll, trapFocus } from './dialog-focus';

describe('dialog-focus', () => {
  let container: HTMLElement;
  let first: HTMLButtonElement;
  let last: HTMLButtonElement;

  beforeEach(() => {
    container = document.createElement('div');
    container.innerHTML = `
      <button id="a">A</button>
      <button id="skip" disabled>X</button>
      <a href="#x" id="b">B</a>
      <button id="c">C</button>`;
    document.body.appendChild(container);
    first = container.querySelector('#a') as HTMLButtonElement;
    last = container.querySelector('#c') as HTMLButtonElement;
  });

  afterEach(() => container.remove());

  it('FOCUSABLE_SELECTOR ignora controles desabilitados', () => {
    const found = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR)).map((e) => e.id);
    expect(found).toEqual(['a', 'b', 'c']);
  });

  it('Tab no último foca o primeiro', () => {
    last.focus();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    trapFocus(ev, container, document);
    expect(ev.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(first);
  });

  it('Shift+Tab no primeiro foca o último', () => {
    first.focus();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true });
    trapFocus(ev, container, document);
    expect(ev.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(last);
  });

  it('Tab no meio não interfere', () => {
    (container.querySelector('#b') as HTMLElement).focus();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    trapFocus(ev, container, document);
    expect(ev.defaultPrevented).toBeFalse();
  });

  it('lockBodyScroll trava e devolve o valor anterior', () => {
    document.body.style.overflow = 'auto';
    const unlock = lockBodyScroll(document);
    expect(document.body.style.overflow).toBe('hidden');
    unlock();
    expect(document.body.style.overflow).toBe('auto');
    document.body.style.overflow = '';
  });

  it('Tab com o foco fora do contêiner (ex.: corpo da página) leva ao primeiro', () => {
    (document.activeElement as HTMLElement | null)?.blur();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    trapFocus(ev, container, document);
    expect(ev.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(first);
  });

  it('Shift+Tab com o foco fora do contêiner leva ao último', () => {
    const outside = document.createElement('button');
    document.body.appendChild(outside);
    outside.focus();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true });
    trapFocus(ev, container, document);
    expect(document.activeElement).toBe(last);
    outside.remove();
  });

  describe('inertOutside', () => {
    it('marca como inert os irmãos de cada ancestral (ex.: navbar) e restaura sem tocar no que já era inert', () => {
      const shell = document.createElement('div');
      shell.innerHTML = `<header id="nav"></header><main id="main"><div id="page" inert></div><div id="host"><i id="inner"></i></div></main>`;
      document.body.appendChild(shell);
      const host = shell.querySelector('#host') as HTMLElement;
      const restore = inertOutside(host, document);
      expect(shell.querySelector('#nav')!.hasAttribute('inert')).toBeTrue();
      expect(shell.querySelector('#page')!.hasAttribute('inert')).toBeTrue();
      expect(shell.querySelector('#inner')!.hasAttribute('inert')).toBeFalse();
      expect(host.hasAttribute('inert')).toBeFalse();
      restore();
      expect(shell.querySelector('#nav')!.hasAttribute('inert')).toBeFalse();
      expect(shell.querySelector('#page')!.hasAttribute('inert')).toBeTrue();
      shell.remove();
    });
  });
});

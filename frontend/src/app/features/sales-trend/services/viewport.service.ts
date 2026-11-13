/**
 * Serviço reativo para detecção de viewport mobile vs desktop (Design Plan §8).
 * Provê signal isCompact (< 768px: modo cartões; >= 768px: modo tabela ledger).
 */
import { DestroyRef, Injectable, inject, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class ViewportService {
  private readonly destroyRef = inject(DestroyRef);
  private readonly mediaQuery =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(max-width: 767.98px)')
      : null;

  readonly isCompact = signal<boolean>(this.mediaQuery ? this.mediaQuery.matches : false);

  constructor() {
    if (this.mediaQuery) {
      const handler = (e: MediaQueryListEvent): void => {
        this.isCompact.set(e.matches);
      };
      this.mediaQuery.addEventListener('change', handler);
      this.destroyRef.onDestroy(() => {
        this.mediaQuery?.removeEventListener('change', handler);
      });
    }
  }
}

/**
 * Serviço reativo para detecção de viewport mobile vs desktop (Design Plan §8).
 * Provê signal isCompact (< 768px: modo cartões; >= 768px: modo tabela ledger).
 */
import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class ViewportService {
  private readonly mediaQuery = typeof window !== 'undefined'
    ? window.matchMedia('(max-width: 767.98px)')
    : null;

  readonly isCompact = signal<boolean>(this.mediaQuery ? this.mediaQuery.matches : false);

  constructor() {
    if (this.mediaQuery) {
      this.mediaQuery.addEventListener('change', (e) => {
        this.isCompact.set(e.matches);
      });
    }
  }
}

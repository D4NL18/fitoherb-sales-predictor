import { Injectable, signal } from '@angular/core';

/**
 * Coordena os popovers `<app-info-help>` da tela para garantir no máximo 1 aberto por vez.
 */
@Injectable({ providedIn: 'root' })
export class InfoHelpCoordinatorService {
  private readonly _activeHelpId = signal<string | null>(null);

  /** Identificador do guia contextual atualmente aberto, ou `null` quando nenhum está visível. */
  readonly activeHelpId = this._activeHelpId.asReadonly();

  open(id: string): void {
    this._activeHelpId.set(id);
  }

  close(id?: string): void {
    if (id === undefined || this._activeHelpId() === id) {
      this._activeHelpId.set(null);
    }
  }

  toggle(id: string): void {
    if (this._activeHelpId() === id) {
      this._activeHelpId.set(null);
      return;
    }
    this._activeHelpId.set(id);
  }
}

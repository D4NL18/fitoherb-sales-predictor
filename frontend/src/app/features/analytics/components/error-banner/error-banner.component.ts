/**
 * Banner de falha técnica (rede, timeout, 5xx, `ANL-00x`) com "Tentar de novo" (Design Plan §6.4).
 * Burro. Nunca exibe `detail`, stacktrace nem instrução de terminal: só a mensagem fixa de tela.
 */
import { Component, output } from '@angular/core';

@Component({
  selector: 'app-error-banner',
  standalone: true,
  templateUrl: './error-banner.component.html',
  styleUrl: './error-banner.component.scss',
})
export class ErrorBannerComponent {
  readonly retry = output<void>();
}

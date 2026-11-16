/**
 * Banner de falha técnica (rede, timeout, 5xx, `ANL-00x` / `ELA-00x`) com ação de retry (Design Plan §6.4).
 * Burro. Nunca exibe `detail`, stacktrace nem instrução de terminal: só a mensagem fixa de tela.
 */
import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-error-banner',
  standalone: true,
  templateUrl: './error-banner.component.html',
  styleUrl: './error-banner.component.scss',
})
export class ErrorBannerComponent {
  readonly message = input<string>('Não foi possível buscar as sugestões agora. Tente de novo em instantes.');
  readonly code = input<string | null>(null);
  readonly retryLabel = input<string>('Tentar de novo');
  readonly retry = output<void>();
}

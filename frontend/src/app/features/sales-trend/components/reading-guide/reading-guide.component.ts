/**
 * Guia de leitura expansível explicando regras de negócio, selos e comparações (Design Plan §5.8).
 */
import { ChangeDetectionStrategy, Component, ElementRef, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-reading-guide',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <details #guideDetails class="reading-guide-details" (keydown.escape)="onEscape($event)">
      <summary #guideSummary class="guide-summary">
        <span class="guide-chevron" aria-hidden="true">›</span>
        <svg class="guide-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
        <span>Como ler esta tabela?</span>
      </summary>

      <div class="guide-content">
        <ul class="guide-list">
          <li>
            <strong>Modos de tendência:</strong> no modo <em>Mês pontual</em>, compara o mês-base diretamente com o mês de 1, 3, 6 ou 12 meses atrás. No modo <em>Média do período</em>, compara o mês-base com a média mensal de vendas do período anterior.
          </li>
          <li>
            <strong>Direção (▲, ▼ e ▬):</strong> triângulo para cima indica crescimento percentual; triângulo para baixo indica retração; barra horizontal indica estabilidade em 0,0%.
          </li>
          <li>
            <strong>Valores absolutos (›):</strong> clique na seta ao lado do produto ou fornecedor para expandir os números absolutos (atual vs anterior) e o detalhamento por produto.
          </li>
          <li>
            <strong>Contribuição (p.p.):</strong> dentro de cada fornecedor expandido, indica quantos pontos percentuais cada produto somou ou subtraiu na variação do fornecedor.
          </li>
          <li>
            <strong>Selo "Novo":</strong> produto que vendeu no período atual mas não teve nenhuma venda líquida no período anterior. Não calcula percentual para evitar divisões irreais.
          </li>
          <li>
            <strong>Selo "Devoluções &gt; vendas":</strong> devoluções abateram as vendas e o líquido resultou em valor negativo, ajustado para zero para o cálculo de variação.
          </li>
          <li>
            <strong>Traço "—" (Sem base):</strong> quando a base de vendas anterior cobre menos de 50% dos dias da janela (histórico insuficiente) ou não houve movimento nos dois períodos.
          </li>
          <li>
            <strong>Escopo:</strong> apenas produtos ativos do catálogo atual com movimentação no histórico de 24 meses.
          </li>
        </ul>
      </div>
    </details>
  `,
  styles: [`
    .reading-guide-details {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      padding: var(--space-2) var(--space-4);
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    .guide-summary {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      min-height: 40px;
      padding: var(--space-1) var(--space-2);
      margin-left: calc(var(--space-2) * -1);
      border-radius: var(--radius-xs);
      font-weight: 600;
      color: var(--brand-primary);
      cursor: pointer;
      user-select: none;
      list-style: none;

      &::-webkit-details-marker {
        display: none;
      }

      &:hover {
        color: var(--brand-primary-hover);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .guide-chevron {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      line-height: 1;
      transition: transform var(--transition-fast);
    }

    .reading-guide-details[open] .guide-chevron {
      transform: rotate(90deg);
    }

    .guide-icon {
      color: var(--brand-primary);
      flex-shrink: 0;
    }

    .guide-content {
      margin-top: var(--space-2);
      padding-top: var(--space-3);
      padding-bottom: var(--space-2);
      border-top: 1px solid var(--border-subtle);
    }

    .guide-list {
      list-style-type: disc;
      padding-left: var(--space-5);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
      line-height: 1.45;
      margin: 0;

      li strong {
        color: var(--text-primary);
      }
    }
  `],
})
export class ReadingGuideComponent {
  private readonly detailsEl = viewChild<ElementRef<HTMLDetailsElement>>('guideDetails');
  private readonly summaryEl = viewChild<ElementRef<HTMLElement>>('guideSummary');

  onEscape(event: Event): void {
    const details = this.detailsEl()?.nativeElement;
    if (details?.open) {
      event.preventDefault();
      details.open = false;
      this.summaryEl()?.nativeElement.focus();
    }
  }
}

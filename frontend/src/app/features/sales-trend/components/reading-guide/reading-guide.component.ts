/**
 * Guia de leitura expansível explicando regras de negócio, selos e comparações (Design Plan §5.8).
 */
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-reading-guide',
  standalone: true,
  imports: [CommonModule],
  template: `
    <details class="reading-guide-details">
      <summary class="guide-summary">
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
            <strong>Direção (▲ e ▼):</strong> triângulo para cima indica crescimento percentual; triângulo para baixo indica retração. Valores próximos de zero são exibidos sem sinal (0,0%).
          </li>
          <li>
            <strong>Selo "Novo":</strong> produto que vendeu no período atual mas não teve nenhuma venda líquida no período anterior. Não calcula percentual para evitar divisões irreais.
          </li>
          <li>
            <strong>Selo "Devoluções > vendas":</strong> devoluções abateram as vendas e o líquido resultou em valor negativo, ajustado para zero para o cálculo de variação.
          </li>
          <li>
            <strong>Traço "—" (Sem base):</strong> quando a base de vendas anterior cobre menos de 50% dos dias da janela (histórico insuficiente).
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
      padding: var(--space-3, 12px) var(--space-4, 16px);
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    .guide-summary {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2, 8px);
      font-weight: 600;
      color: var(--brand-primary);
      cursor: pointer;
      user-select: none;

      &:hover {
        color: var(--brand-primary-hover);
      }
    }

    .guide-icon {
      color: var(--brand-primary);
      flex-shrink: 0;
    }

    .guide-content {
      margin-top: var(--space-3, 12px);
      padding-top: var(--space-3, 12px);
      border-top: 1px solid var(--border-subtle);
    }

    .guide-list {
      list-style-type: disc;
      padding-left: var(--space-5, 20px);
      display: flex;
      flex-direction: column;
      gap: var(--space-2, 8px);
      line-height: 1.4;

      li strong {
        color: var(--text-primary);
      }
    }
  `],
})
export class ReadingGuideComponent {}

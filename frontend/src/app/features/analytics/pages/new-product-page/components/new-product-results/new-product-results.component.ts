/**
 * Painel de resultados da simulação de Produto Novo (F2, P-143 a P-149).
 * Dumb component (OnPush): Selo Conservador, degradação graciosa F1, Card de Viabilidade,
 * Gráfico de Faixas + Tabela Mensal, Bloco Segregado P75 e Lista Top-10 Similares.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { NewProductForecastData, SimilarProductItem } from '../../../../models/new-product.model';
import { BrlPipe, PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';
import { NewProductBandChartComponent } from '../new-product-band-chart/new-product-band-chart.component';

interface ViabilityBadgeView {
  tagClass: 'tag-positive' | 'tag-warning' | 'tag-neutral' | 'tag-info';
  accentClass: 'accent-positive' | 'accent-warning' | 'accent-neutral' | 'accent-info';
  label: string;
}

const MONTH_ABBR: Record<number, string> = {
  1: 'Jan',
  2: 'Fev',
  3: 'Mar',
  4: 'Abr',
  5: 'Mai',
  6: 'Jun',
  7: 'Jul',
  8: 'Ago',
  9: 'Set',
  10: 'Out',
  11: 'Nov',
  12: 'Dez',
};

const NEUTRAL_CONFIDENCES = new Set(['BAIXA', 'INSUFICIENTE', 'PADRAO']);

@Component({
  selector: 'app-new-product-results',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, PtPercentPipe, NewProductBandChartComponent],
  templateUrl: './new-product-results.component.html',
  styleUrl: './new-product-results.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProductResultsComponent {
  readonly data = input.required<NewProductForecastData>();
  readonly isDirty = input<boolean>(false);
  readonly selectedSimilarSku = input<string | null>(null);

  readonly explainSimilar = output<{ similar: SimilarProductItem; trigger: HTMLElement | null }>();

  protected readonly horizonMonths = computed(() => {
    const reqHorizon = this.data().inputSummary.horizonMonths;
    return reqHorizon ?? (this.data().monthlyForecast.length || 3);
  });

  protected readonly isSeasonalityNeutral = computed(() => {
    const forecast = this.data();
    if (forecast.seasonalityStatus === 'FALLBACK_NEUTRAL' || forecast.seasonalityStatus === 'UNAVAILABLE') {
      return true;
    }
    return forecast.monthlyForecast.some(
      (item) => item.seasonalityConfidence !== undefined && NEUTRAL_CONFIDENCES.has(item.seasonalityConfidence),
    );
  });

  protected readonly viabilityBadge = computed<ViabilityBadgeView>(() => {
    const fin = this.data().financialViability;
    if (fin.viavel === true) {
      return {
        tagClass: 'tag-positive',
        accentClass: 'accent-positive',
        label: 'Viável para Lançamento',
      };
    }
    if (fin.viavel === false) {
      return {
        tagClass: 'tag-warning',
        accentClass: 'accent-warning',
        label: 'Margem Abaixo do Esperado',
      };
    }
    if (fin.custoUnitario === null) {
      return {
        tagClass: 'tag-neutral',
        accentClass: 'accent-neutral',
        label: 'Simulação de Demanda (sem custo)',
      };
    }
    return {
      tagClass: 'tag-info',
      accentClass: 'accent-info',
      label: 'Margem Calculada (sem meta mínima)',
    };
  });

  protected formatMonthLabel(month: number, calendarMonth?: number): string {
    if (!calendarMonth) return `M${month}`;
    const abbr = MONTH_ABBR[calendarMonth];
    return abbr ? `M${month} · ${abbr}` : `M${month}`;
  }

  protected formatLaunchMonthQty(months: readonly number[], index: number): string {
    return index < months.length ? String(months[index]) : '—';
  }

  protected onExplain(similar: SimilarProductItem, event: Event): void {
    const trigger = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    this.explainSimilar.emit({ similar, trigger });
  }

  protected onOpenFirstSimilar(event: Event): void {
    const first = this.data().similarsUsed[0];
    if (!first) return;
    const trigger = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    this.explainSimilar.emit({ similar: first, trigger });
  }
}

/**
 * Gráfico SVG acessível e colorblind-safe de faixas de lançamento (P10, Conservador, P50).
 * Nunca plota o Teto Maduro (P75) na curva principal para cumprir P-147.3 / P-149.
 */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MonthlyForecastItem } from '../../../../models/new-product.model';
import { formatDecimal } from '../../../../utils/pt-br-format';

interface ChartPoint {
  x: number;
  p10Y: number;
  consY: number;
  p50Y: number;
  label: string;
  p10: number;
  conservative: number;
  p50: number;
  trianglePoints: string;
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

const SVG_WIDTH = 620;
const SVG_HEIGHT = 240;
const PAD_LEFT = 54;
const PAD_RIGHT = 32;
const PAD_TOP = 26;
const PAD_BOTTOM = 38;
const PLOT_WIDTH = SVG_WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_HEIGHT = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM;

@Component({
  selector: 'app-new-product-band-chart',
  standalone: true,
  templateUrl: './new-product-band-chart.component.html',
  styleUrl: './new-product-band-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProductBandChartComponent {
  readonly items = input.required<MonthlyForecastItem[]>();

  protected readonly viewBox = `0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`;
  protected readonly plotBottom = PAD_TOP + PLOT_HEIGHT;
  protected readonly padLeft = PAD_LEFT;
  protected readonly plotRight = SVG_WIDTH - PAD_RIGHT;

  protected readonly maxScale = computed(() => {
    const list = this.items();
    if (list.length === 0) return 10;
    const maxVal = Math.max(
      ...list.map((item) => Math.max(item.p50Quantity, item.conservativeQuantity, item.p10Quantity)),
      1,
    );
    return Math.ceil(maxVal * 1.15);
  });

  protected readonly yTicks = computed(() => {
    const max = this.maxScale();
    const ratios = [0, 0.5, 1];
    return ratios.map((ratio) => {
      const value = Math.round(max * ratio);
      const y = PAD_TOP + PLOT_HEIGHT - ratio * PLOT_HEIGHT;
      return { y, label: formatDecimal(value, 0) };
    });
  });

  protected readonly points = computed<ChartPoint[]>(() => {
    const list = this.items();
    const max = this.maxScale();
    const count = list.length;

    return list.map((item, idx) => {
      const x =
        count === 1
          ? PAD_LEFT + PLOT_WIDTH / 2
          : PAD_LEFT + (idx / (count - 1)) * PLOT_WIDTH;

      const toY = (val: number) => PAD_TOP + PLOT_HEIGHT - (Math.max(0, val) / max) * PLOT_HEIGHT;
      const p10Y = toY(item.p10Quantity);
      const consY = toY(item.conservativeQuantity);
      const p50Y = toY(item.p50Quantity);

      const cal = item.calendarMonth ? ` · ${MONTH_ABBR[item.calendarMonth] ?? ''}` : '';
      const label = `M${item.month}${cal}`;

      // Triângulo invertido (▽) centrado em (x, p10Y)
      const trianglePoints = `${x - 5},${p10Y - 4} ${x + 5},${p10Y - 4} ${x},${p10Y + 5}`;

      return {
        x,
        p10Y,
        consY,
        p50Y,
        label,
        p10: item.p10Quantity,
        conservative: item.conservativeQuantity,
        p50: item.p50Quantity,
        trianglePoints,
      };
    });
  });

  protected readonly bandPolygonPoints = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return '';
    const upper = pts.map((p) => `${p.x},${p.p50Y}`).join(' ');
    const lower = [...pts].reverse().map((p) => `${p.x},${p.p10Y}`).join(' ');
    return `${upper} ${lower}`;
  });

  protected readonly p10Polyline = computed(() =>
    this.points()
      .map((p) => `${p.x},${p.p10Y}`)
      .join(' '),
  );

  protected readonly consPolyline = computed(() =>
    this.points()
      .map((p) => `${p.x},${p.consY}`)
      .join(' '),
  );

  protected readonly p50Polyline = computed(() =>
    this.points()
      .map((p) => `${p.x},${p.p50Y}`)
      .join(' '),
  );

  protected readonly ariaSummary = computed(() => {
    const pts = this.points();
    if (pts.length === 0) return 'Gráfico de faixas de previsão mensal sem dados.';
    const summary = pts
      .map(
        (p) =>
          `${p.label}: P10 ${formatDecimal(p.p10, 0)} un, Conservador ${formatDecimal(p.conservative, 0)} un, Mediana P50 ${formatDecimal(p.p50, 0)} un`,
      )
      .join('; ');
    return `Projeção mensal de lançamento em unidades (${summary}).`;
  });

  protected formatQty(val: number): string {
    return formatDecimal(val, 0);
  }
}

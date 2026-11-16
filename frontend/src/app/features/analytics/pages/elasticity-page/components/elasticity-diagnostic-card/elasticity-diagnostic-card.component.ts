import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { InfoHelpComponent } from '../../../../components/info-help/info-help.component';
import { ProductElasticityMetrics, ProductHeader } from '../../../../models/elasticity.models';
import { BrlPipe, PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';
import { ELASTICITY_HELP_COPY } from '../../../../utils/elasticity-help-copy';
import {
  computeUnitMargin,
  formatPriceReactionHint,
  formatPriceReactionRangeHint,
  formatUnits,
  getClassificationMeta,
  getConfidenceMeta,
} from '../../../../utils/elasticity-view';
import { formatDecimal } from '../../../../utils/pt-br-format';

@Component({
  selector: 'app-elasticity-diagnostic-card',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, PtPercentPipe, InfoHelpComponent],
  templateUrl: './elasticity-diagnostic-card.component.html',
  styleUrl: './elasticity-diagnostic-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticityDiagnosticCardComponent {
  readonly product = input.required<ProductHeader>();
  readonly elasticity = input.required<ProductElasticityMetrics>();

  protected readonly helpCopy = ELASTICITY_HELP_COPY;

  protected readonly classificationMeta = computed(() =>
    getClassificationMeta(this.elasticity().classification),
  );
  protected readonly confidenceMeta = computed(() =>
    getConfidenceMeta(this.elasticity().confidenceLevel),
  );
  protected readonly formattedStock = computed(() => formatUnits(this.product().stock));

  protected readonly priceReactionHint = computed(() =>
    formatPriceReactionHint(this.elasticity().coefficient),
  );
  protected readonly priceReactionRangeHint = computed(() =>
    formatPriceReactionRangeHint(this.elasticity().confidenceInterval),
  );
  protected readonly unitMargin = computed(() =>
    computeUnitMargin(this.product().currentPrice, this.product().costPrice),
  );
  protected readonly formattedUnitMarginPct = computed(
    () => `${formatDecimal(this.unitMargin().marginPct, 1)}%`,
  );
}

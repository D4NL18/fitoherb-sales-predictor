import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { ProductElasticityMetrics, ProductHeader } from '../../../../models/elasticity.models';
import { BrlPipe, PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';
import { formatUnits, getClassificationMeta, getConfidenceMeta } from '../../../../utils/elasticity-view';

@Component({
  selector: 'app-elasticity-diagnostic-card',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, PtPercentPipe],
  templateUrl: './elasticity-diagnostic-card.component.html',
  styleUrl: './elasticity-diagnostic-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticityDiagnosticCardComponent {
  readonly product = input.required<ProductHeader>();
  readonly elasticity = input.required<ProductElasticityMetrics>();

  protected readonly classificationMeta = computed(() =>
    getClassificationMeta(this.elasticity().classification),
  );
  protected readonly confidenceMeta = computed(() =>
    getConfidenceMeta(this.elasticity().confidenceLevel),
  );
  protected readonly formattedStock = computed(() => formatUnits(this.product().stock));
}

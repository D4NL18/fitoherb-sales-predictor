import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import {
  CannibalizationKpis,
  TopCategoryHighlight,
} from '../../../../models/cannibalization.model';
import {
  PtDecimalPipe,
  SignedBrlPipe,
  SignedPercentPipe,
} from '../../../../pipes/pt-br-format.pipes';

@Component({
  selector: 'app-cannibalization-kpi-strip',
  standalone: true,
  imports: [PtDecimalPipe, SignedBrlPipe, SignedPercentPipe],
  templateUrl: './cannibalization-kpi-strip.component.html',
  styleUrl: './cannibalization-kpi-strip.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CannibalizationKpiStripComponent {
  readonly kpis = input.required<CannibalizationKpis>();
  readonly topCategory = input<TopCategoryHighlight | null>(null);
}

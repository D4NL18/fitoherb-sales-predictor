import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-elasticity-skeleton',
  standalone: true,
  templateUrl: './elasticity-skeleton.component.html',
  styleUrl: './elasticity-skeleton.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticitySkeletonComponent {
  protected readonly metricPlaceholders = [0, 1, 2, 3];
  protected readonly simPlaceholders = [0, 1, 2];
  protected readonly rowPlaceholders = [0, 1, 2, 3, 4];
}

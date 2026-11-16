import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-elasticity-skeleton',
  standalone: true,
  templateUrl: './elasticity-skeleton.component.html',
  styleUrl: './elasticity-skeleton.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticitySkeletonComponent {
  protected readonly cardPlaceholders = [0, 1, 2, 3];
}

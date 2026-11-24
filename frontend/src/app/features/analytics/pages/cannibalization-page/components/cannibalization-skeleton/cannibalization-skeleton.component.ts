import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-cannibalization-skeleton',
  standalone: true,
  templateUrl: './cannibalization-skeleton.component.html',
  styleUrl: './cannibalization-skeleton.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CannibalizationSkeletonComponent {
  readonly slowQuery = input<boolean>(false);
  protected readonly kpiPlaceholders = [1, 2, 3, 4];
  protected readonly rows = [1, 2, 3, 4, 5, 6];
}

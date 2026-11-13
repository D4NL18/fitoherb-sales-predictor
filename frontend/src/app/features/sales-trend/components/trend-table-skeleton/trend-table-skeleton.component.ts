/**
 * Skeleton Loader com geometria idêntica à tabela ou cartões de tendência (Design Plan §4.2).
 * Consome classes globais .skeleton-line e .skeleton-box com pulso sólido.
 */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-table-skeleton',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (variant() === 'table') {
      <div class="skeleton-table-wrapper" aria-hidden="true">
        <table class="skeleton-table">
          <thead>
            <tr>
              <th class="col-exp"><span class="skeleton-box" style="width: 20px"></span></th>
              <th class="col-item"><span class="skeleton-box" style="width: 140px"></span></th>
              <th class="col-win"><span class="skeleton-box" style="width: 80px"></span></th>
              <th class="col-win"><span class="skeleton-box" style="width: 80px"></span></th>
              <th class="col-win"><span class="skeleton-box" style="width: 80px"></span></th>
              <th class="col-win"><span class="skeleton-box" style="width: 80px"></span></th>
            </tr>
          </thead>
          <tbody>
            @for (i of rowArray(); track i) {
              <tr>
                <td class="col-exp"><span class="skeleton-box" style="width: 18px; height: 18px"></span></td>
                <td class="col-item">
                  <span class="skeleton-line" style="width: 70%; margin-bottom: 4px"></span>
                  <span class="skeleton-line" style="width: 40%"></span>
                </td>
                <td class="col-win"><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td class="col-win"><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td class="col-win"><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td class="col-win"><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else {
      <div class="skeleton-cards-wrapper" aria-hidden="true">
        @for (i of rowArray(); track i) {
          <div class="skeleton-card">
            <span class="skeleton-line" style="width: 80%; height: 1.1em; margin-bottom: 8px"></span>
            <span class="skeleton-line" style="width: 45%; margin-bottom: 16px"></span>
            <div class="skeleton-grid">
              <span class="skeleton-box" style="height: 54px"></span>
              <span class="skeleton-box" style="height: 54px"></span>
              <span class="skeleton-box" style="height: 54px"></span>
              <span class="skeleton-box" style="height: 54px"></span>
            </div>
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .skeleton-table-wrapper {
      width: 100%;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      overflow-x: auto;
    }

    .skeleton-table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
      table-layout: fixed;

      th, td {
        padding: var(--space-3) var(--space-4);
        border-bottom: 1px solid var(--border-subtle);
        vertical-align: middle;
      }

      th {
        background-color: var(--bg-table-header);
      }

      .col-exp {
        width: 44px;
      }

      .col-win {
        width: 15.5%;
        text-align: right;
      }
    }

    .skeleton-cards-wrapper {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .skeleton-card {
      padding: var(--space-4);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
    }

    .skeleton-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: var(--space-2);
    }
  `],
})
export class TrendTableSkeletonComponent {
  readonly rows = input<number>(10);
  readonly variant = input<'table' | 'cards'>('table');

  readonly rowArray = computed(() => Array.from({ length: this.rows() }, (_, i) => i));
}

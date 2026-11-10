/**
 * Skeleton Loader com geometria idêntica à tabela ou cartões de tendência (Design Plan §4.2).
 * Consome classes globais .skeleton-line e .skeleton-box com pulso sólido.
 */
import { Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-table-skeleton',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (variant() === 'table') {
      <div class="skeleton-table-wrapper" aria-hidden="true">
        <table class="skeleton-table">
          <thead>
            <tr>
              <th style="width: 40px"><span class="skeleton-box" style="width: 20px"></span></th>
              <th><span class="skeleton-box" style="width: 140px"></span></th>
              <th><span class="skeleton-box" style="width: 80px"></span></th>
              <th><span class="skeleton-box" style="width: 80px"></span></th>
              <th><span class="skeleton-box" style="width: 80px"></span></th>
              <th><span class="skeleton-box" style="width: 80px"></span></th>
            </tr>
          </thead>
          <tbody>
            @for (i of rowArray(); track i) {
              <tr>
                <td><span class="skeleton-box" style="width: 18px; height: 18px"></span></td>
                <td>
                  <span class="skeleton-line" style="width: 70%; margin-bottom: 4px"></span>
                  <span class="skeleton-line" style="width: 40%"></span>
                </td>
                <td><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
                <td><span class="skeleton-box" style="width: 75px; height: 24px"></span></td>
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
              <span class="skeleton-box" style="height: 48px"></span>
              <span class="skeleton-box" style="height: 48px"></span>
              <span class="skeleton-box" style="height: 48px"></span>
              <span class="skeleton-box" style="height: 48px"></span>
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
      overflow: hidden;
    }

    .skeleton-table {
      width: 100%;
      border-collapse: collapse;

      th, td {
        padding: var(--space-3, 12px) var(--space-4, 16px);
        border-bottom: 1px solid var(--border-subtle);
        vertical-align: middle;
      }

      th {
        background-color: var(--bg-table-header);
      }
    }

    .skeleton-cards-wrapper {
      display: flex;
      flex-direction: column;
      gap: var(--space-3, 12px);
    }

    .skeleton-card {
      padding: var(--space-4, 16px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
    }

    .skeleton-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: var(--space-2, 8px);
    }
  `],
})
export class TrendTableSkeletonComponent {
  readonly rows = input<number>(10);
  readonly variant = input<'table' | 'cards'>('table');

  readonly rowArray = computed(() => Array.from({ length: this.rows() }, (_, i) => i));
}

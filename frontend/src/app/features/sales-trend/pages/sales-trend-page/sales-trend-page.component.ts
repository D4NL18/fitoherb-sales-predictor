/**
 * Componente principal da página /tendencia-vendas (P-086, Design Plan §4).
 * Único componente inteligente da feature, provê o SalesTrendStore.
 */
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { SalesTrendStore } from '../../services/sales-trend.store';
import { queryParamsToState } from '../../utils/trend-url';

@Component({
  selector: 'app-sales-trend-page',
  standalone: true,
  imports: [CommonModule],
  providers: [SalesTrendStore],
  template: `
    <main class="trend-page" role="main">
      <div class="trend-container">
        <h1>Tendência de Vendas por Item</h1>
      </div>
    </main>
  `,
  styles: [`
    .trend-page {
      padding: var(--space-4, 1rem);
    }
  `],
})
export class SalesTrendPageComponent implements OnInit {
  readonly store = inject(SalesTrendStore);
  private readonly route = inject(ActivatedRoute);

  ngOnInit(): void {
    const params = queryParamsToState(this.route.snapshot.queryParams);
    this.store.init(params);
  }
}

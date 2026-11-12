/**
 * Página de Elasticidade-Preço por Produto e Cliente (F5 / P-095..P-105).
 * Suporte integral aos 8 estados interativos com Signals reativos.
 */
import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AnalyticsService } from '../../services/analytics.service';
import {
  CustomerElasticityItem,
  ElasticitySimulationResponse,
  ProductElasticityDetail,
  ProductElasticityResponse,
  SimulationImpactData,
} from '../../models/elasticity.models';

export type PageStatus = 'initial' | 'loading' | 'success' | 'empty' | 'error';

@Component({
  selector: 'app-elasticity-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './elasticity-page.component.html',
  styleUrl: './elasticity-page.component.scss',
})
export class ElasticityPageComponent implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);

  // Estados da página
  protected readonly status = signal<PageStatus>('initial');
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly errorCode = signal<string | null>(null);

  // Dados do produto consultado
  protected readonly searchSku = signal<string>('1001');
  protected readonly productData = signal<ProductElasticityDetail | null>(null);

  // Simulador de Reajuste
  protected readonly priceChangePct = signal<number>(5.0);
  protected readonly selectedCustomerCode = signal<number | null>(null);
  protected readonly simulationResult = signal<SimulationImpactData | null>(null);
  protected readonly isSimulating = signal<boolean>(false);
  protected readonly simulationError = signal<string | null>(null);

  // Paginação de Clientes
  protected readonly clientPageLimit = 10;
  protected readonly clientPageOffset = signal<number>(0);
  protected readonly totalClients = signal<number>(0);

  ngOnInit(): void {
    // Carregar produto inicial de demonstração se disponível
    if (this.searchSku()) {
      this.loadProductElasticity();
    }
  }

  /** Consulta a elasticidade do SKU informado (P-096, P-099). */
  loadProductElasticity(): void {
    const skuNum = Number(this.searchSku().trim());
    if (!skuNum || skuNum <= 0) {
      this.status.set('error');
      this.errorCode.set('ELA-004');
      this.errorMessage.set('Informe um código de produto (SKU) numérico válido.');
      return;
    }

    this.status.set('loading');
    this.errorMessage.set(null);
    this.errorCode.set(null);
    this.clientPageOffset.set(0);

    this.analyticsService.getProductElasticity(skuNum, { limit: 50, offset: 0 }).subscribe({
      next: (resp: ProductElasticityResponse) => {
        this.productData.set(resp.data);
        this.totalClients.set(resp.data.customers.length);
        this.status.set(resp.data.customers.length > 0 ? 'success' : 'success');
        // Disparar simulação inicial com o percentual default (+5%)
        this.runSimulation();
      },
      error: (err) => {
        this.status.set('error');
        const code = err.error?.error?.code || 'ELA-001';
        const msg = err.error?.error?.message || 'Produto não encontrado ou sem histórico suficiente.';
        this.errorCode.set(code);
        this.errorMessage.set(msg);
      },
    });
  }

  /** Executa o cálculo da simulação de preço (P-101). */
  runSimulation(): void {
    const data = this.productData();
    if (!data) return;

    const pct = this.priceChangePct();
    if (pct < -50 || pct > 100) {
      this.simulationError.set('O percentual deve estar entre -50% e +100%.');
      return;
    }

    this.isSimulating.set(true);
    this.simulationError.set(null);

    this.analyticsService
      .simulatePriceChange({
        sku: data.product.code,
        customerCode: this.selectedCustomerCode(),
        priceChangePct: pct,
      })
      .subscribe({
        next: (resp: ElasticitySimulationResponse) => {
          this.simulationResult.set(resp.data);
          this.isSimulating.set(false);
        },
        error: (err) => {
          this.simulationError.set(err.error?.error?.message || 'Erro ao simular variação de preço.');
          this.isSimulating.set(false);
        },
      });
  }

  /** Define percentual rápido de reajuste. */
  setPriceQuickAdjust(pct: number): void {
    this.priceChangePct.set(pct);
    this.runSimulation();
  }

  /** Seleciona um cliente para simulação individualizada. */
  selectCustomerForSimulation(code: number | null): void {
    this.selectedCustomerCode.set(code);
    this.runSimulation();
  }

  /** Próxima página de clientes. */
  nextPage(): void {
    const maxOffset = this.totalClients() - this.clientPageLimit;
    if (this.clientPageOffset() < maxOffset) {
      this.clientPageOffset.update((v) => v + this.clientPageLimit);
    }
  }

  /** Página anterior de clientes. */
  prevPage(): void {
    if (this.clientPageOffset() > 0) {
      this.clientPageOffset.update((v) => Math.max(0, v - this.clientPageLimit));
    }
  }

  /** Lista de clientes exibida na página atual. */
  displayedCustomers(): CustomerElasticityItem[] {
    const customers = this.productData()?.customers || [];
    const offset = this.clientPageOffset();
    return customers.slice(offset, offset + this.clientPageLimit);
  }
}

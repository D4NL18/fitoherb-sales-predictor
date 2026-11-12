/**
 * Página principal da aba Churn de Clientes (Design Plan §4; P-117 a P-127).
 * Tabela priorizada por Score de Retenção, KPIs de impacto, filtros e drawer lateral.
 */
import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AnalyticsService } from '../../services/analytics.service';
import {
  ChurnCustomerItem,
  ChurnSummaryKpi,
  CustomerChurnDetailData,
} from '../../models/churn.model';
import { PageRequest } from '../../models/analytics.model';
import { CustomerChurnDrawerComponent } from '../../components/customer-churn-drawer/customer-churn-drawer.component';

@Component({
  selector: 'app-churn-page',
  standalone: true,
  imports: [CommonModule, CustomerChurnDrawerComponent],
  templateUrl: './churn-page.component.html',
  styleUrl: './churn-page.component.scss',
})
export class ChurnPageComponent implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);

  readonly statusFilter = signal<string>('EM_RISCO');
  readonly customers = signal<ChurnCustomerItem[]>([]);
  readonly resumo = signal<ChurnSummaryKpi | null>(null);
  readonly loading = signal<boolean>(true);
  readonly error = signal<string | null>(null);

  // Paginação
  readonly limit = 50;
  readonly offset = signal<number>(0);
  readonly totalItems = signal<number>(0);

  // Drawer
  readonly isDrawerOpen = signal<boolean>(false);
  readonly drawerLoading = signal<boolean>(false);
  readonly selectedCustomer = signal<CustomerChurnDetailData | null>(null);

  // Exportação CSV
  readonly isExporting = signal<boolean>(false);

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.loading.set(true);
    this.error.set(null);

    const pageReq: PageRequest = { limit: this.limit, offset: this.offset() };
    const currentStatus = this.statusFilter();

    if (currentStatus === 'INATIVO_RECUPERACAO') {
      this.analyticsService.getInactiveChurn(pageReq).subscribe({
        next: (res) => {
          const mapped: ChurnCustomerItem[] = res.data.items.map((item) => ({
            customerCode: item.customerCode,
            status: 'INATIVO_RECUPERACAO',
            diasSemComprar: item.diasSemComprar,
            gapTipico: null,
            diasReferencia: 60,
            fatorTempo: 2.0,
            faturamentoMedioMensal: item.faturamentoMedioMensal,
            scorePrioridade: item.faturamentoMedioMensal * 2.0,
            historicoCurto: item.historicoCurto,
          }));
          this.customers.set(mapped);
          this.totalItems.set(res.meta.totalItems);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Não foi possível carregar a lista de inativos. Verifique sua conexão.');
          this.loading.set(false);
        },
      });
    } else {
      this.analyticsService.getChurnCustomers(currentStatus, pageReq).subscribe({
        next: (res) => {
          this.customers.set(res.data.items);
          this.resumo.set(res.data.resumo);
          this.totalItems.set(res.meta.totalItems);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Falha ao carregar clientes em risco de churn.');
          this.loading.set(false);
        },
      });
    }
  }

  setFilter(status: string): void {
    if (this.statusFilter() === status) return;
    this.statusFilter.set(status);
    this.offset.set(0);
    this.fetchData();
  }

  nextPage(): void {
    if (this.offset() + this.limit < this.totalItems()) {
      this.offset.update((o) => o + this.limit);
      this.fetchData();
    }
  }

  prevPage(): void {
    if (this.offset() > 0) {
      this.offset.update((o) => Math.max(0, o - this.limit));
      this.fetchData();
    }
  }

  openCustomerDetail(customer: ChurnCustomerItem): void {
    this.isDrawerOpen.set(true);
    this.drawerLoading.set(true);
    this.selectedCustomer.set(null);

    this.analyticsService.getCustomerChurnDetail(customer.customerCode).subscribe({
      next: (res) => {
        this.selectedCustomer.set(res.data);
        this.drawerLoading.set(false);
      },
      error: () => {
        // Fallback com dados da tabela se endpoint falhar
        this.selectedCustomer.set({
          customerCode: customer.customerCode,
          status: customer.status,
          diasSemComprar: customer.diasSemComprar,
          dataUltimoPedido: null,
          gapTipico: customer.gapTipico,
          diasReferencia: customer.diasReferencia,
          fatorTempo: customer.fatorTempo,
          faturamentoMedioMensal: customer.faturamentoMedioMensal,
          scorePrioridade: customer.scorePrioridade,
          historicoCurto: customer.historicoCurto,
          variacaoReceitaTrimestralPct: null,
          historicoMensal: [],
          produtosPerdidos: [],
        });
        this.drawerLoading.set(false);
      },
    });
  }

  closeDrawer(): void {
    this.isDrawerOpen.set(false);
    this.selectedCustomer.set(null);
  }

  exportCsv(): void {
    this.isExporting.set(true);
    const items = this.customers();
    if (!items.length) {
      this.isExporting.set(false);
      return;
    }

    const headers = ['Codigo Cliente', 'Status', 'Dias Sem Comprar', 'Cadencia Tipica (dias)', 'Faturamento Medio Mensal (R$)', 'Score Prioridade (R$)'];
    const rows = items.map((c) => [
      c.customerCode,
      c.status,
      c.diasSemComprar,
      c.gapTipico ?? '—',
      c.faturamentoMedioMensal.toFixed(2),
      c.scorePrioridade.toFixed(2),
    ]);

    const csvContent = '\uFEFF' + [headers.join(';'), ...rows.map((r) => r.join(';'))].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `churn-clientes-${this.statusFilter().toLowerCase()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    this.isExporting.set(false);
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  }
}

import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { InventoryService } from '../../services/inventory.service';
import {
  InventoryKPIs,
  InventoryParams,
  InventoryProductItem,
  InventoryStatus,
  SupplierItem,
} from '../../models/inventory.model';

@Component({
  selector: 'app-inventory-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './inventory-page.component.html',
  styleUrls: ['./inventory-page.component.scss']
})
export class InventoryPageComponent implements OnInit {
  private readonly inventoryService = inject(InventoryService);
  private readonly CACHE_KEY = 'fitoherb_inventory_cache_v1';

  // Parâmetros de Simulação
  readonly historyWindowDays = signal<number>(60);
  readonly leadTimeDays = signal<number>(15);
  readonly targetCoverageDays = signal<number>(30);
  readonly serviceLevel = signal<number>(0.95);
  readonly budgetLimit = signal<number | null>(null);

  // Estados de Carregamento e Modais
  readonly isLoading = signal<boolean>(false);
  readonly isDownloading = signal<boolean>(false);
  readonly isSettingsModalOpen = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);
  readonly lastCalculatedAt = signal<string | null>(null);

  // Dados Retornados
  readonly kpis = signal<InventoryKPIs | null>(null);
  readonly products = signal<InventoryProductItem[]>([]);
  readonly suppliers = signal<SupplierItem[]>([]);

  // Filtros, Busca, Ordenação e Paginação
  readonly searchTerm = signal<string>('');
  readonly selectedSupplier = signal<string>('TODOS');
  readonly statusFilter = signal<string>('ALL'); // ALL | CRITICAL_STOCKOUT | REORDER_NEEDED | HEALTHY | OVERSTOCK
  readonly curvaAbcFilter = signal<string>('ALL'); // ALL | A | B | C
  readonly sortColumn = signal<keyof InventoryProductItem | ''>('status');
  readonly sortDirection = signal<'asc' | 'desc'>('asc');
  readonly currentPage = signal<number>(1);
  readonly pageSize = signal<number>(20);

  // Lista Filtrada e Ordenada
  readonly filteredProducts = computed<InventoryProductItem[]>(() => {
    let list = this.products();
    const search = this.searchTerm().toLowerCase().trim();
    const sup = this.selectedSupplier();
    const status = this.statusFilter();
    const abc = this.curvaAbcFilter();

    if (search) {
      list = list.filter(p =>
        p.descricao.toLowerCase().includes(search) ||
        p.codigo.toString().includes(search) ||
        p.ean.includes(search)
      );
    }

    if (sup && sup !== 'TODOS') {
      list = list.filter(p => p.fornecedor.toUpperCase() === sup.toUpperCase());
    }

    if (status !== 'ALL') {
      list = list.filter(p => p.status === status);
    }

    if (abc !== 'ALL') {
      list = list.filter(p => p.curvaAbc === abc);
    }

    // Ordenação
    const col = this.sortColumn();
    const dir = this.sortDirection();
    if (col) {
      list = [...list].sort((a, b) => {
        let valA: any = a[col];
        let valB: any = b[col];

        if (col === 'status') {
          const rankMap: Record<string, number> = {
            CRITICAL_STOCKOUT: 0,
            REORDER_NEEDED: 1,
            HEALTHY: 2,
            OVERSTOCK: 3
          };
          valA = rankMap[a.status] ?? 4;
          valB = rankMap[b.status] ?? 4;
        }

        if (valA < valB) return dir === 'asc' ? -1 : 1;
        if (valA > valB) return dir === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return list;
  });

  // Paginação
  readonly totalPages = computed<number>(() => {
    return Math.ceil(this.filteredProducts().length / this.pageSize()) || 1;
  });

  readonly paginatedProducts = computed<InventoryProductItem[]>(() => {
    const page = this.currentPage();
    const size = this.pageSize();
    const start = (page - 1) * size;
    return this.filteredProducts().slice(start, start + size);
  });

  ngOnInit(): void {
    this.loadSuppliers();
    this.loadCachedPrediction();
  }

  loadSuppliers(): void {
    this.inventoryService.getSuppliers().subscribe({
      next: (res) => {
        if (res?.data) {
          this.suppliers.set(res.data);
        }
      },
      error: (err) => console.warn('Não foi possível carregar fornecedores:', err)
    });
  }

  calculateInventory(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const params: InventoryParams = {
      historyWindowDays: this.historyWindowDays(),
      leadTimeDays: this.leadTimeDays(),
      targetCoverageDays: this.targetCoverageDays(),
      serviceLevel: this.serviceLevel(),
      fornecedor: this.selectedSupplier() !== 'TODOS' ? this.selectedSupplier() : null,
      budgetLimit: this.budgetLimit()
    };

    this.inventoryService.predict(params).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res?.data) {
          this.kpis.set(res.data.kpis);
          this.products.set(res.data.produtos);
          this.currentPage.set(1);
          const now = new Date().toLocaleString('pt-BR');
          this.lastCalculatedAt.set(now);
          this.saveCache(res.data.kpis, res.data.produtos, now);
          this.successMessage.set('Plano de estoque e compras calculado com sucesso!');
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(err?.error?.detail || 'Erro ao calcular sugestão de compras e estoque.');
      }
    });
  }

  downloadCsv(): void {
    if (this.products().length === 0) return;
    this.isDownloading.set(true);

    const params: InventoryParams = {
      historyWindowDays: this.historyWindowDays(),
      leadTimeDays: this.leadTimeDays(),
      targetCoverageDays: this.targetCoverageDays(),
      serviceLevel: this.serviceLevel(),
      fornecedor: this.selectedSupplier() !== 'TODOS' ? this.selectedSupplier() : null,
      budgetLimit: this.budgetLimit()
    };

    this.inventoryService.exportCsv(params).subscribe({
      next: (blob) => {
        this.isDownloading.set(false);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const fornecStr = this.selectedSupplier() !== 'TODOS' ? `_${this.selectedSupplier().toLowerCase()}` : '';
        a.download = `fitoherb_plano_compras${fornecStr}_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        this.isDownloading.set(false);
        this.errorMessage.set('Falha ao exportar arquivo CSV.');
      }
    });
  }

  toggleSort(column: keyof InventoryProductItem): void {
    if (this.sortColumn() === column) {
      this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('asc');
    }
  }

  setPage(page: number): void {
    if (page >= 1 && page <= this.totalPages()) {
      this.currentPage.set(page);
    }
  }

  openSettingsModal(): void {
    this.isSettingsModalOpen.set(true);
  }

  closeSettingsModal(): void {
    this.isSettingsModalOpen.set(false);
  }

  applyModalSettings(): void {
    this.closeSettingsModal();
    this.calculateInventory();
  }

  private saveCache(kpis: InventoryKPIs, produtos: InventoryProductItem[], savedAt: string): void {
    try {
      const payload = { kpis, produtos, savedAt };
      localStorage.setItem(this.CACHE_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('Erro ao salvar cache local:', e);
    }
  }

  private loadCachedPrediction(): void {
    try {
      const raw = localStorage.getItem(this.CACHE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.kpis && parsed?.produtos) {
          this.kpis.set(parsed.kpis);
          this.products.set(parsed.produtos);
          this.lastCalculatedAt.set(parsed.savedAt || null);
          return;
        }
      }
    } catch (e) {
      console.warn('Erro ao recuperar cache local:', e);
    }
    // Se não houver cache, dispara o primeiro cálculo
    this.calculateInventory();
  }
}

/**
 * Componente de página de Previsão de Estoque e Compras (`app-inventory-page`).
 *
 * Gerencia o estado reativo (Signals) da Política Mín/Máx por dias de cobertura (P-053 a P-056),
 * separando a política efetivamente aplicada (`appliedPolicy`) do rascunho em edição no modal
 * e validando o cache local v3 (CA-12, ADR-001 DA-08/DA-09).
 */
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import {
  InventoryService,
  extractInventoryErrorMessage,
} from '../../services/inventory.service';
import {
  InventoryKPIs,
  InventoryParams,
  InventoryPolicy,
  InventoryProductItem,
  InventoryStatusCode,
  SupplierItem,
} from '../../models/inventory.model';
import {
  DEFAULT_HISTORY_WINDOW_DAYS,
  DEFAULT_LEAD_TIME_DAYS,
  DEFAULT_MAX_COVERAGE_DAYS,
  DEFAULT_MIN_COVERAGE_DAYS,
  HISTORY_WINDOW_DAYS_RANGE,
  INVENTORY_CACHE_KEY,
  LEAD_TIME_DAYS_RANGE,
  LEGACY_INVENTORY_CACHE_KEYS,
  MAX_COVERAGE_DAYS_RANGE,
  MIN_COVERAGE_DAYS_RANGE,
} from '../../inventory.constants';
import {
  InventoryCachePayload,
  InventoryPolicyIssue,
  isInventoryCachePayload,
  validateInventoryPolicy,
} from '../../utils/inventory-policy.validation';

/** Campos de produto suportados na ordenação de colunas da tabela. */
export type SortableProductField = keyof InventoryProductItem;

const ALL_SUPPLIERS_OPTION = 'TODOS';
const ALL_FILTER_OPTION = 'ALL';
const DEFAULT_PAGE_NUMBER = 1;
const DEFAULT_PAGE_SIZE = 20;
const SKELETON_KPI_COUNT = 5;
const SKELETON_ROW_COUNT = 10;
const ISO_DATE_SLICE_END = 10;
const UNKNOWN_STATUS_RANK = 4;

const STATUS_SORT_RANK: Readonly<Record<InventoryStatusCode, number>> = {
  CRITICAL_STOCKOUT: 0,
  REORDER_NEEDED: 1,
  HEALTHY: 2,
  OVERSTOCK: 3,
};

const DEFAULT_POLICY: InventoryPolicy = {
  historyWindowDays: DEFAULT_HISTORY_WINDOW_DAYS,
  leadTimeDays: DEFAULT_LEAD_TIME_DAYS,
  minCoverageDays: DEFAULT_MIN_COVERAGE_DAYS,
  maxCoverageDays: DEFAULT_MAX_COVERAGE_DAYS,
};

@Component({
  selector: 'app-inventory-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './inventory-page.component.html',
  styleUrls: ['./inventory-page.component.scss'],
})
export class InventoryPageComponent implements OnInit {
  private readonly inventoryService = inject(InventoryService);

  /** Faixas dos controles deslizantes expostas ao template (A1, A4, A5). */
  readonly historyWindowRange = HISTORY_WINDOW_DAYS_RANGE;
  readonly leadTimeRange = LEAD_TIME_DAYS_RANGE;
  readonly minCoverageRange = MIN_COVERAGE_DAYS_RANGE;
  readonly maxCoverageRange = MAX_COVERAGE_DAYS_RANGE;

  /** Listas auxiliares para renderização de Skeleton Loaders (Design Plan §6.1). */
  readonly skeletonKpis = Array.from({ length: SKELETON_KPI_COUNT }, (_, i) => i);
  readonly skeletonRows = Array.from({ length: SKELETON_ROW_COUNT }, (_, i) => i);

  /** Sinais de rascunho dos parâmetros editáveis no modal (P-053.2). */
  readonly historyWindowDays = signal<number>(DEFAULT_HISTORY_WINDOW_DAYS);
  readonly leadTimeDays = signal<number>(DEFAULT_LEAD_TIME_DAYS);
  readonly minCoverageDays = signal<number>(DEFAULT_MIN_COVERAGE_DAYS);
  readonly maxCoverageDays = signal<number>(DEFAULT_MAX_COVERAGE_DAYS);

  /** Política efetivamente aplicada ao último cálculo concluído (ADR-001 DA-08). */
  readonly appliedPolicy = signal<InventoryPolicy>({ ...DEFAULT_POLICY });

  /** Validação cruzada em tempo real dos parâmetros em edição no modal (P-053.3, A2). */
  readonly policyIssue = computed<InventoryPolicyIssue | null>(() =>
    validateInventoryPolicy({
      minCoverageDays: this.minCoverageDays(),
      maxCoverageDays: this.maxCoverageDays(),
      leadTimeDays: this.leadTimeDays(),
    })
  );

  readonly isMinMaxInvalid = computed<boolean>(
    () => this.maxCoverageDays() <= this.minCoverageDays()
  );

  readonly isLeadTimeInvalid = computed<boolean>(
    () => this.leadTimeDays() >= this.maxCoverageDays()
  );

  readonly canApplySettings = computed<boolean>(() => this.policyIssue() === null);

  /** Estados de carregamento, exportação e feedback da tela. */
  readonly isLoading = signal<boolean>(false);
  readonly isDownloading = signal<boolean>(false);
  readonly isSettingsModalOpen = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);
  readonly lastCalculatedAt = signal<string | null>(null);

  /** Dados retornados pela API. */
  readonly kpis = signal<InventoryKPIs | null>(null);
  readonly products = signal<InventoryProductItem[]>([]);
  readonly suppliers = signal<SupplierItem[]>([]);

  /** Filtros, busca, ordenação e paginação local. */
  readonly searchTerm = signal<string>('');
  readonly selectedSupplier = signal<string>(ALL_SUPPLIERS_OPTION);
  readonly statusFilter = signal<string>(ALL_FILTER_OPTION);
  readonly curvaAbcFilter = signal<string>(ALL_FILTER_OPTION);
  readonly sortColumn = signal<SortableProductField | ''>('status');
  readonly sortDirection = signal<'asc' | 'desc'>('asc');
  readonly currentPage = signal<number>(DEFAULT_PAGE_NUMBER);
  readonly pageSize = signal<number>(DEFAULT_PAGE_SIZE);

  /** Produtos filtrados e ordenados segundo os controles ativos na tela. */
  readonly filteredProducts = computed<InventoryProductItem[]>(() => {
    const filtered = this.applyProductFilters(this.products());
    const col = this.sortColumn();
    if (!col) {
      return filtered;
    }
    const dir = this.sortDirection();
    return [...filtered].sort((a, b) => this.compareProductItems(a, b, col, dir));
  });

  readonly totalPages = computed<number>(() => {
    return Math.ceil(this.filteredProducts().length / this.pageSize()) || DEFAULT_PAGE_NUMBER;
  });

  readonly paginatedProducts = computed<InventoryProductItem[]>(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredProducts().slice(start, start + this.pageSize());
  });

  ngOnInit(): void {
    this.purgeLegacyCacheKeys();
    this.loadSuppliers();
    if (!this.loadCachedPrediction()) {
      this.calculateInventory();
    }
  }

  /** Carrega a lista de fornecedores/laboratórios do catálogo (P-047.1). */
  loadSuppliers(): void {
    this.inventoryService.getSuppliers().subscribe({
      next: (res) => {
        if (res?.data) {
          this.suppliers.set(res.data);
        }
      },
      error: () => {
        this.suppliers.set([]);
      },
    });
  }

  /** Executa o cálculo da Política Mín/Máx na API e sincroniza estado e cache v3. */
  calculateInventory(): void {
    if (!this.canApplySettings()) {
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const requestParams = this.buildPredictParams();
    this.inventoryService.predict(requestParams).subscribe({
      next: (res) => this.handlePredictSuccess(res?.data, requestParams),
      error: (err: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.errorMessage.set(extractInventoryErrorMessage(err));
      },
    });
  }

  /** Exporta o CSV usando estritamente a política aplicada ao resultado visível (P-056.6). */
  downloadCsv(): void {
    if (this.products().length === 0 || this.isLoading()) {
      return;
    }
    this.isDownloading.set(true);
    const params = this.buildPredictParams(this.appliedPolicy());

    this.inventoryService.exportCsv(params).subscribe({
      next: (blob) => {
        this.isDownloading.set(false);
        this.triggerCsvBrowserDownload(blob);
      },
      error: (err: HttpErrorResponse) => {
        this.isDownloading.set(false);
        this.errorMessage.set(extractInventoryErrorMessage(err));
      },
    });
  }

  /** Alterna a coluna ou direção de ordenação da tabela. */
  toggleSort(column: SortableProductField): void {
    if (this.sortColumn() === column) {
      this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
      return;
    }
    this.sortColumn.set(column);
    this.sortDirection.set('asc');
  }

  /** Atualiza a página ativa respeitando os limites de paginação. */
  setPage(page: number): void {
    if (page >= DEFAULT_PAGE_NUMBER && page <= this.totalPages()) {
      this.currentPage.set(page);
    }
  }

  /** Limpa todos os filtros locais de busca, status, curva ABC e fornecedor. */
  resetFilters(): void {
    this.searchTerm.set('');
    this.statusFilter.set(ALL_FILTER_OPTION);
    this.curvaAbcFilter.set(ALL_FILTER_OPTION);
    this.selectedSupplier.set(ALL_SUPPLIERS_OPTION);
    this.currentPage.set(DEFAULT_PAGE_NUMBER);
  }

  /** Abre o modal sincronizando os controles com a última política aplicada. */
  openSettingsModal(): void {
    this.syncDraftWithPolicy(this.appliedPolicy());
    this.isSettingsModalOpen.set(true);
  }

  /** Descarta alterações em rascunho, restaura a política aplicada e fecha o modal. */
  cancelSettingsModal(): void {
    this.syncDraftWithPolicy(this.appliedPolicy());
    this.isSettingsModalOpen.set(false);
  }

  /** Fecha o modal descartando qualquer edição não aplicada. */
  closeSettingsModal(): void {
    this.cancelSettingsModal();
  }

  /** Restaura os padrões 60 / 15 / 30 / 60 no rascunho do modal sem disparar requisição. */
  restoreDefaultPolicy(): void {
    this.syncDraftWithPolicy(DEFAULT_POLICY);
  }

  /** Valida a política em rascunho e dispara o recálculo se não houver violação (CA-06). */
  applySettingsAndRecalculate(): void {
    if (!this.canApplySettings()) {
      return;
    }
    this.isSettingsModalOpen.set(false);
    this.calculateInventory();
  }

  /** Alias para compatibilidade com chamadas de aplicação do modal. */
  applyModalSettings(): void {
    this.applySettingsAndRecalculate();
  }

  private buildPredictParams(policyOverride?: InventoryPolicy): InventoryParams {
    const source = policyOverride ?? {
      historyWindowDays: this.historyWindowDays(),
      leadTimeDays: this.leadTimeDays(),
      minCoverageDays: this.minCoverageDays(),
      maxCoverageDays: this.maxCoverageDays(),
    };
    const supplier = this.selectedSupplier();
    return {
      historyWindowDays: source.historyWindowDays,
      minCoverageDays: source.minCoverageDays,
      maxCoverageDays: source.maxCoverageDays,
      leadTimeDays: source.leadTimeDays,
      fornecedor: supplier !== ALL_SUPPLIERS_OPTION ? supplier : null,
    };
  }

  private handlePredictSuccess(
    data: { politica?: InventoryPolicy; kpis: InventoryKPIs; produtos: InventoryProductItem[] } | undefined,
    sentParams: InventoryParams
  ): void {
    this.isLoading.set(false);
    if (!data) {
      return;
    }
    const effectivePolicy: InventoryPolicy = data.politica ?? {
      historyWindowDays: sentParams.historyWindowDays,
      leadTimeDays: sentParams.leadTimeDays,
      minCoverageDays: sentParams.minCoverageDays,
      maxCoverageDays: sentParams.maxCoverageDays,
    };
    const savedAt = new Date().toLocaleString('pt-BR');
    this.appliedPolicy.set(effectivePolicy);
    this.syncDraftWithPolicy(effectivePolicy);
    this.kpis.set(data.kpis);
    this.products.set(data.produtos);
    this.currentPage.set(DEFAULT_PAGE_NUMBER);
    this.lastCalculatedAt.set(savedAt);
    this.saveCache({ politica: effectivePolicy, kpis: data.kpis, produtos: data.produtos, savedAt });
    this.successMessage.set('Plano de estoque e compras calculado com sucesso!');
  }

  private syncDraftWithPolicy(policy: InventoryPolicy): void {
    this.historyWindowDays.set(policy.historyWindowDays);
    this.leadTimeDays.set(policy.leadTimeDays);
    this.minCoverageDays.set(policy.minCoverageDays);
    this.maxCoverageDays.set(policy.maxCoverageDays);
  }

  private purgeLegacyCacheKeys(): void {
    try {
      for (const legacyKey of LEGACY_INVENTORY_CACHE_KEYS) {
        localStorage.removeItem(legacyKey);
      }
    } catch {
      // Ignora bloqueios de acesso ao Web Storage em navegação restrita.
    }
  }

  private saveCache(payload: InventoryCachePayload): void {
    try {
      localStorage.setItem(INVENTORY_CACHE_KEY, JSON.stringify(payload));
    } catch {
      // Falha de cota ou bloqueio de storage não interrompe a jornada do comprador.
    }
  }

  /**
   * Restaura o cache local v3 caso passe pelo type guard `isInventoryCachePayload` (CA-12).
   * Remove entradas corrompidas ou legadas e retorna `false` para forçar novo cálculo.
   */
  loadCachedPrediction(): boolean {
    try {
      const raw = localStorage.getItem(INVENTORY_CACHE_KEY);
      if (!raw) {
        return false;
      }
      const parsed: unknown = JSON.parse(raw);
      if (!isInventoryCachePayload(parsed)) {
        localStorage.removeItem(INVENTORY_CACHE_KEY);
        return false;
      }
      this.appliedPolicy.set(parsed.politica);
      this.syncDraftWithPolicy(parsed.politica);
      this.kpis.set(parsed.kpis);
      this.products.set(parsed.produtos);
      this.lastCalculatedAt.set(parsed.savedAt);
      return true;
    } catch {
      localStorage.removeItem(INVENTORY_CACHE_KEY);
      return false;
    }
  }

  private applyProductFilters(items: InventoryProductItem[]): InventoryProductItem[] {
    const search = this.searchTerm().toLowerCase().trim();
    const supplier = this.selectedSupplier();
    const status = this.statusFilter();
    const abc = this.curvaAbcFilter();

    return items.filter(
      (item) =>
        this.matchesSearch(item, search) &&
        this.matchesSupplier(item, supplier) &&
        (status === ALL_FILTER_OPTION || item.status === status) &&
        (abc === ALL_FILTER_OPTION || item.curvaAbc === abc)
    );
  }

  private matchesSearch(item: InventoryProductItem, search: string): boolean {
    if (!search) {
      return true;
    }
    return (
      item.descricao.toLowerCase().includes(search) ||
      item.codigo.toString().includes(search) ||
      item.ean.includes(search)
    );
  }

  private matchesSupplier(item: InventoryProductItem, supplier: string): boolean {
    if (!supplier || supplier === ALL_SUPPLIERS_OPTION) {
      return true;
    }
    return item.fornecedor.toUpperCase() === supplier.toUpperCase();
  }

  private compareProductItems(
    a: InventoryProductItem,
    b: InventoryProductItem,
    column: SortableProductField,
    direction: 'asc' | 'desc'
  ): number {
    const multiplier = direction === 'asc' ? 1 : -1;
    if (column === 'status') {
      const rankA = STATUS_SORT_RANK[a.status] ?? UNKNOWN_STATUS_RANK;
      const rankB = STATUS_SORT_RANK[b.status] ?? UNKNOWN_STATUS_RANK;
      return (rankA - rankB) * multiplier;
    }
    const valA = a[column];
    const valB = b[column];
    if (typeof valA === 'number' && typeof valB === 'number') {
      return (valA - valB) * multiplier;
    }
    return String(valA).localeCompare(String(valB), 'pt-BR') * multiplier;
  }

  private triggerCsvBrowserDownload(blob: Blob): void {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const supplier = this.selectedSupplier();
    const supplierSuffix =
      supplier !== ALL_SUPPLIERS_OPTION ? `_${supplier.toLowerCase().replace(/[^a-z0-9]+/g, '_')}` : '';
    const dateStamp = new Date().toISOString().slice(0, ISO_DATE_SLICE_END);
    anchor.href = url;
    anchor.download = `fitoherb_plano_compras${supplierSuffix}_${dateStamp}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  }
}

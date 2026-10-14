import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PricingService } from '../../services/pricing.service';
import { PricingParams, PricingSummary, ProductPreview, CachedPredictionState } from '../../models/pricing.model';

@Component({
  selector: 'app-pricing-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pricing-page.component.html',
  styleUrls: ['./pricing-page.component.scss']
})
export class PricingPageComponent implements OnInit, OnDestroy {
  private readonly pricingService = inject(PricingService);
  private progressTimer: any = null;
  private readonly CACHE_KEY = 'fitoherb_pricing_cache_v1';

  // Modal de Parâmetros e Cache Persistente (Regras P-025 a P-027)
  readonly isSettingsModalOpen = signal<boolean>(false);
  readonly lastSavedDate = signal<string | null>(null);

  // Modal de Tutorial Interativo / Onboarding (Regras P-028 a P-030)
  readonly isTutorialModalOpen = signal<boolean>(false);
  readonly tutorialCurrentStep = signal<number>(1);
  readonly tutorialTotalSteps = 5;

  // Hiperparâmetros reativos via Signals (valores em porcentagem para exibição amigável)
  readonly kRatio = signal<number>(25);                 // 15% a 35%
  readonly variableKRatio = signal<boolean>(true);      // Trava dinâmica otimizada por âncora (Regra P-017)
  readonly topAnchors = signal<number>(15);             // 5 a 30 SKUs
  readonly halfLifeDays = signal<number>(100);          // 30 a 365 dias
  readonly anchorDiscount = signal<number>(-10);        // -15% a -5%
  readonly compMaxIncrease = signal<number>(6);         // +1% a +8%
  readonly stressDrop = signal<number>(5);              // 1% a 10%
  readonly autonomousSkuPricing = signal<boolean>(true);// Autonomia Granular por SKU (P-048 a P-052)

  // Estados da Aplicação
  readonly isLoading = signal<boolean>(false);
  readonly isDownloading = signal<boolean>(false);
  readonly isAutoTuning = signal<boolean>(false);
  readonly selectedStrategy = signal<'balanced' | 'profit_focused' | 'volume_focused'>('balanced');
  readonly isStrategyDropdownOpen = signal<boolean>(false);
  readonly gaGenerationsRun = signal<number>(0);
  readonly gaBestFitness = signal<number | null>(null);

  readonly selectedStrategyTitle = computed<string>(() => {
    switch (this.selectedStrategy()) {
      case 'volume_focused': return 'Leve';
      case 'profit_focused': return 'Agressivo';
      default: return 'Equilibrado';
    }
  });

  readonly selectedStrategySubtitle = computed<string>(() => {
    switch (this.selectedStrategy()) {
      case 'volume_focused': return 'Foco em Volume de Vendas e Giro Rápido';
      case 'profit_focused': return 'Foco em Margem e Rentabilidade Máxima';
      default: return 'Equilíbrio entre Margem e Volume';
    }
  });

  // Barra de Progresso Reativa (Carregamento Inicial, Equilibrar e Calcular)
  readonly isProgressActive = signal<boolean>(false);
  readonly progressPercent = signal<number>(0);
  readonly progressMessage = signal<string>('');

  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  // Dados Retornados
  readonly dbStatus = signal<any>(null);
  readonly summary = signal<PricingSummary | null>(null);
  readonly previewProducts = signal<ProductPreview[]>([]);

  // Filtros, Busca, Ordenação e Paginação da Tabela Completa (Regras P-019 a P-021)
  readonly searchTerm = signal<string>('');
  readonly roleFilter = signal<string>('ALL'); // 'ALL' | 'ANCHOR' | 'COMP' | 'NEUTRAL' | 'CHANGED'
  readonly brandFilter = signal<string>('ALL');
  readonly sortColumn = signal<keyof ProductPreview | ''>('');
  readonly sortDirection = signal<'asc' | 'desc'>('asc');
  readonly pageSize = signal<number>(25); // 10, 25, 50, 100, -1
  readonly currentPage = signal<number>(1);

  readonly availableBrands = computed<string[]>(() => {
    const set = new Set<string>();
    for (const p of this.previewProducts()) {
      if (p.fornecedor) set.add(p.fornecedor.trim());
    }
    return Array.from(set).sort();
  });

  readonly roleCounts = computed(() => {
    const list = this.previewProducts();
    let anchors = 0;
    let comps = 0;
    let neutrals = 0;
    for (const p of list) {
      if (p.papelEstrategico.includes('ÂNCORA')) anchors++;
      else if (p.papelEstrategico.includes('COMPENSADOR')) comps++;
      else neutrals++;
    }
    return {
      all: list.length,
      anchors,
      comps,
      neutrals,
      changed: anchors + comps
    };
  });

  readonly filteredProducts = computed<ProductPreview[]>(() => {
    let list = this.previewProducts();
    const term = this.searchTerm().trim().toLowerCase();
    const role = this.roleFilter();
    const brand = this.brandFilter();
    const sortCol = this.sortColumn();
    const sortDir = this.sortDirection();

    // 1. Busca textual global
    if (term) {
      list = list.filter((p) =>
        String(p.codigo).includes(term) ||
        p.descricao.toLowerCase().includes(term) ||
        p.fornecedor.toLowerCase().includes(term) ||
        p.regraComercial.toLowerCase().includes(term)
      );
    }

    // 2. Filtro por papel estratégico
    if (role !== 'ALL') {
      if (role === 'ANCHOR') {
        list = list.filter((p) => p.papelEstrategico.includes('ÂNCORA'));
      } else if (role === 'COMP') {
        list = list.filter((p) => p.papelEstrategico.includes('COMPENSADOR'));
      } else if (role === 'NEUTRAL') {
        list = list.filter((p) => p.papelEstrategico === 'NEUTRO');
      } else if (role === 'CHANGED') {
        list = list.filter((p) => p.papelEstrategico !== 'NEUTRO');
      }
    }

    // 3. Filtro por marca
    if (brand !== 'ALL') {
      list = list.filter((p) => p.fornecedor.trim() === brand);
    }

    // 4. Ordenação por coluna
    if (sortCol) {
      list = [...list].sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        if (valA === null || valA === undefined) valA = '';
        if (valB === null || valB === undefined) valB = '';

        if (typeof valA === 'number' && typeof valB === 'number') {
          return sortDir === 'asc' ? valA - valB : valB - valA;
        }
        const strA = String(valA).toLowerCase();
        const strB = String(valB).toLowerCase();
        return sortDir === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
      });
    }

    return list;
  });

  readonly totalPages = computed<number>(() => {
    const size = this.pageSize();
    if (size <= 0) return 1;
    return Math.max(1, Math.ceil(this.filteredProducts().length / size));
  });

  readonly paginatedProducts = computed<ProductPreview[]>(() => {
    const list = this.filteredProducts();
    const size = this.pageSize();
    if (size <= 0) return list;

    const page = Math.min(this.currentPage(), this.totalPages());
    const start = (page - 1) * size;
    return list.slice(start, start + size);
  });

  readonly paginationSummary = computed<string>(() => {
    const total = this.filteredProducts().length;
    if (total === 0) return 'Nenhum produto encontrado';
    const size = this.pageSize();
    if (size <= 0) return `Exibindo todos os ${total} produtos`;

    const page = Math.min(this.currentPage(), this.totalPages());
    const start = (page - 1) * size + 1;
    const end = Math.min(page * size, total);
    return `Mostrando ${start} a ${end} de ${total} produtos (Página ${page} de ${this.totalPages()})`;
  });

  readonly paginationPages = computed<number[]>(() => {
    const total = this.totalPages();
    const current = this.currentPage();
    const pages: number[] = [];

    const startPage = Math.max(1, current - 3);
    const endPage = Math.min(total, current + 3);

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    return pages;
  });

  ngOnInit(): void {
    // 1. Carrega primeiro do cache local rápido (para exibição imediata)
    this.loadPredictionFromCache();

    // 2. Busca a última previsão compartilhada centralizada no servidor (para todos os usuários verem o mesmo resultado)
    this.pricingService.getLatestPrediction().subscribe({
      next: (res) => {
        if (res && res.data && res.data.summary) {
          this.applyPredictionState(res.data);
          // Atualiza cache local sincronizado
          try {
            localStorage.setItem(this.CACHE_KEY, JSON.stringify(res.data));
          } catch (_) {}
        } else if (!this.summary()) {
          // Se ainda não houver previsão compartilhada gravada, calibra uma inicial
          this.selectedStrategy.set('balanced');
          this.runAutoTune(true);
        }
      },
      error: () => {
        if (!this.summary()) {
          this.selectedStrategy.set('balanced');
          this.runAutoTune(true);
        }
      }
    });

    // 3. Pré-carrega a configuração da API e status da conexão com banco SQL Server
    this.pricingService.getConfig().subscribe({
      next: () => {},
      error: () => {}
    });

    this.pricingService.getDbStatus().subscribe({
      next: (res) => {
        this.dbStatus.set(res.data);
      },
      error: () => {}
    });
  }


  ngOnDestroy(): void {
    this.clearProgressTimer();
  }

  get currentParams(): PricingParams {
    return {
      kRatio: this.kRatio() / 100.0,
      variableKRatio: this.variableKRatio(),
      topAnchors: this.topAnchors(),
      halfLifeDays: this.halfLifeDays(),
      anchorMinDiscount: -0.15,
      anchorMaxDiscount: this.anchorDiscount() / 100.0,
      compMaxIncrease: this.compMaxIncrease() / 100.0,
      stressDrop: this.stressDrop() / 100.0,
      autonomousSkuPricing: this.autonomousSkuPricing(),
    };
  }

  toggleAutonomousSkuPricing(): void {
    this.autonomousSkuPricing.update((v) => !v);
    this.runPrediction(
      this.autonomousSkuPricing()
        ? 'Recalculando precificação com decisão autônoma e dinâmica por SKU (P-048 a P-052)...'
        : 'Recalculando precificação com parâmetros uniformes estáticos...'
    );
  }

  toggleVariableKRatio(): void {
    this.variableKRatio.update((v) => !v);
    this.runPrediction(
      this.variableKRatio()
        ? 'Recalculando precificação com travas comerciais dinâmicas por âncora (Regra P-017)...'
        : 'Recalculando precificação com trava comercial uniforme global...'
    );
  }

  onKRatioChange(val: number): void {
    this.kRatio.set(val);
  }

  startProgress(initialMessage: string): void {
    this.clearProgressTimer();
    this.isProgressActive.set(true);
    this.progressPercent.set(15);
    this.progressMessage.set(initialMessage);

    this.progressTimer = setInterval(() => {
      this.progressPercent.update((prev) => {
        if (prev < 70) {
          return prev + Math.floor(Math.random() * 8) + 4;
        } else if (prev < 88) {
          return prev + Math.floor(Math.random() * 4) + 2;
        } else if (prev < 98) {
          return prev + 1;
        }
        return 98;
      });
    }, 150);
  }

  finishProgress(successMessage?: string): void {
    this.clearProgressTimer();
    this.progressPercent.set(100);
    if (successMessage) {
      this.progressMessage.set(successMessage);
    }
    setTimeout(() => {
      this.isProgressActive.set(false);
      this.progressPercent.set(0);
      this.progressMessage.set('');
    }, 350);
  }

  failProgress(): void {
    this.clearProgressTimer();
    this.isProgressActive.set(false);
    this.progressPercent.set(0);
    this.progressMessage.set('');
  }

  private clearProgressTimer(): void {
    if (this.progressTimer) {
      clearInterval(this.progressTimer);
      this.progressTimer = null;
    }
  }

  runPrediction(customMessage?: string): void {
    const msg = customMessage || 'Calculando projeção de preços com parâmetros selecionados...';
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.startProgress(msg);

    this.pricingService.predict(this.currentParams).subscribe({
      next: (res) => {
        this.summary.set(res.data.summary);
        this.previewProducts.set(res.data.previewProducts);
        this.isLoading.set(false);
        this.finishProgress('Projeção calculada com sucesso!');
        this.savePredictionToCache(res.data.summary, res.data.previewProducts);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.failProgress();
        this.errorMessage.set(
          err.error?.detail || err.error?.message || 'Falha ao conectar com a API de precificação (FastAPI na porta 8000).'
        );
      }
    });
  }

  downloadCsv(): void {
    this.isDownloading.set(true);
    this.errorMessage.set(null);
    this.startProgress('Gerando arquivo CSV com a lista completa de produtos...');

    this.pricingService.exportCsv(this.currentParams).subscribe({
      next: (blob) => {
        const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const filename = `precificacao_fitoherb_k${this.kRatio()}_${timestamp}.csv`;
        this.pricingService.downloadBlob(blob, filename);
        this.isDownloading.set(false);
        this.finishProgress('Download concluído com sucesso!');
        this.successMessage.set(`Download concluído: ${filename}`);
        setTimeout(() => this.successMessage.set(null), 4000);
      },
      error: (err) => {
        this.isDownloading.set(false);
        this.failProgress();
        this.errorMessage.set('Erro ao gerar arquivo para download.');
      }
    });
  }

  resetDefaults(): void {
    this.kRatio.set(25);
    this.variableKRatio.set(true);
    this.topAnchors.set(15);
    this.halfLifeDays.set(100);
    this.anchorDiscount.set(-10);
    this.compMaxIncrease.set(6);
    this.stressDrop.set(5);
    this.selectedStrategy.set('balanced');
    this.runPrediction('Restaurando parâmetros padrão e recalculando projeção...');
  }

  runAutoTune(autoPredictAfter = false): void {
    this.clearProgressTimer();
    this.isAutoTuning.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.isProgressActive.set(true);
    this.progressPercent.set(5);
    this.progressMessage.set('Otimizando parâmetros ideais para o perfil selecionado...');

    this.pricingService.autoTuneStream(this.selectedStrategy(), 6).subscribe({
      next: (event) => {
        if (event.type === 'progress') {
          // Atualização realista do andamento do cálculo
          this.progressPercent.set(event.data.percent);
          this.progressMessage.set(event.data.message);
        } else if (event.type === 'complete') {
          const res = event.data;
          const opt = res.data.optimalParams;

          // Atualiza os signals reativos automaticamente
          this.kRatio.set(Math.round(opt.kRatio * 100));
          this.topAnchors.set(opt.topAnchors);
          this.halfLifeDays.set(Math.round(opt.halfLifeDays));
          this.anchorDiscount.set(Math.round(opt.anchorDiscount * 100));
          this.compMaxIncrease.set(Math.round(opt.compMaxIncrease * 100));
          this.stressDrop.set(Math.round(opt.stressDrop * 100));

          this.gaGenerationsRun.set(res.data.generationsRun);
          this.gaBestFitness.set(res.data.bestFitness);
          this.isAutoTuning.set(false);

          const stratLabel = this.selectedStrategy() === 'profit_focused' 
            ? 'Agressivo' 
            : this.selectedStrategy() === 'volume_focused' 
            ? 'Leve' 
            : 'Equilibrado';

          this.finishProgress('Parâmetros otimizados com sucesso!');

          this.successMessage.set(
            `Parâmetros calibrados e aplicados para a estratégia [${stratLabel}]!`
          );
          setTimeout(() => this.successMessage.set(null), 5000);

          if (autoPredictAfter) {
            this.runPrediction('Aplicando precificação com parâmetros calibrados...');
          }
        }
      },
      error: (err) => {
        this.isAutoTuning.set(false);
        this.failProgress();
        this.errorMessage.set(
          err.message || 'Erro ao otimizar os parâmetros de precificação.'
        );
        if (autoPredictAfter) {
          this.runPrediction('Carregando precificação inicial...');
        }
      }
    });
  }

  setRoleFilter(role: string): void {
    this.roleFilter.set(role);
    this.currentPage.set(1);
  }

  setBrandFilter(brand: string): void {
    this.brandFilter.set(brand);
    this.currentPage.set(1);
  }

  setSearchTerm(term: string): void {
    this.searchTerm.set(term);
    this.currentPage.set(1);
  }

  clearSearch(): void {
    this.searchTerm.set('');
    this.currentPage.set(1);
  }

  clearAllFilters(): void {
    this.searchTerm.set('');
    this.roleFilter.set('ALL');
    this.brandFilter.set('ALL');
    this.sortColumn.set('');
    this.currentPage.set(1);
  }

  toggleSort(col: keyof ProductPreview): void {
    if (this.sortColumn() === col) {
      if (this.sortDirection() === 'asc') {
        this.sortDirection.set('desc');
      } else {
        this.sortColumn.set('');
        this.sortDirection.set('asc');
      }
    } else {
      this.sortColumn.set(col);
      this.sortDirection.set('asc');
    }
  }

  goToPage(p: number): void {
    if (p >= 1 && p <= this.totalPages()) {
      this.currentPage.set(p);
    }
  }

  setPageSize(size: any): void {
    this.pageSize.set(Number(size));
    this.currentPage.set(1);
  }

  // Controle do Modal de Parâmetros e Dropdown Customizado (Regras P-025, P-032)
  openSettingsModal(): void {
    this.isStrategyDropdownOpen.set(false);
    this.isSettingsModalOpen.set(true);
  }

  closeSettingsModal(): void {
    this.isStrategyDropdownOpen.set(false);
    this.isSettingsModalOpen.set(false);
  }

  toggleStrategyDropdown(): void {
    this.isStrategyDropdownOpen.update((v) => !v);
  }

  closeStrategyDropdown(): void {
    this.isStrategyDropdownOpen.set(false);
  }

  selectStrategy(strategy: 'volume_focused' | 'balanced' | 'profit_focused'): void {
    this.selectedStrategy.set(strategy);
  }

  confirmStrategyAndRecalculate(): void {
    this.closeStrategyDropdown();
    this.closeSettingsModal();
    this.runAutoTune(true);
  }

  applyManualParameters(): void {
    this.closeSettingsModal();
    this.runPrediction('Recalculando precificação com os parâmetros ajustados...');
  }

  // Controle do Tutorial Interativo / Onboarding (Regras P-028 a P-030)
  openTutorial(): void {
    this.tutorialCurrentStep.set(1);
    this.isTutorialModalOpen.set(true);
  }

  closeTutorial(): void {
    this.isTutorialModalOpen.set(false);
  }

  nextTutorialStep(): void {
    if (this.tutorialCurrentStep() < this.tutorialTotalSteps) {
      this.tutorialCurrentStep.update((s) => s + 1);
    } else {
      this.closeTutorial();
    }
  }

  prevTutorialStep(): void {
    if (this.tutorialCurrentStep() > 1) {
      this.tutorialCurrentStep.update((s) => s - 1);
    }
  }

  setTutorialStep(step: number): void {
    if (step >= 1 && step <= this.tutorialTotalSteps) {
      this.tutorialCurrentStep.set(step);
    }
  }

  // Persistência em Cache Offline-First (Regra P-027)
  private savePredictionToCache(summary: PricingSummary, products: ProductPreview[]): void {
    try {
      const state: CachedPredictionState = {
        summary,
        previewProducts: products,
        params: this.currentParams,
        strategy: this.selectedStrategy(),
        savedAt: new Date().toISOString()
      };
      localStorage.setItem(this.CACHE_KEY, JSON.stringify(state));
      const now = new Date();
      this.lastSavedDate.set(
        `${now.toLocaleDateString('pt-BR')} às ${now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
      );
    } catch (e) {
      console.warn('Falha ao salvar previsão no cache local:', e);
    }
  }

  private applyPredictionState(state: any): boolean {
    if (state && state.summary && state.previewProducts?.length > 0) {
      this.summary.set(state.summary);
      this.previewProducts.set(state.previewProducts);
      if (state.params) {
        const kVal = state.params.kRatio !== undefined ? state.params.kRatio : state.params.k_ratio;
        if (kVal !== undefined) this.kRatio.set(Math.round(kVal * 100));

        const varK = state.params.variableKRatio !== undefined ? state.params.variableKRatio : state.params.variable_k_ratio;
        if (varK !== undefined) this.variableKRatio.set(varK);

        const anchors = state.params.topAnchors !== undefined ? state.params.topAnchors : state.params.top_anchors;
        if (anchors !== undefined) this.topAnchors.set(anchors);

        const halfLife = state.params.halfLifeDays !== undefined ? state.params.halfLifeDays : state.params.half_life_days;
        if (halfLife !== undefined) this.halfLifeDays.set(halfLife);

        const disc = state.params.anchorMaxDiscount !== undefined ? state.params.anchorMaxDiscount : state.params.anchor_max_discount;
        if (disc !== undefined) this.anchorDiscount.set(Math.round(disc * 100));

        const compInc = state.params.compMaxIncrease !== undefined ? state.params.compMaxIncrease : state.params.comp_max_increase;
        if (compInc !== undefined) this.compMaxIncrease.set(Math.round(compInc * 100));

        const stress = state.params.stressDrop !== undefined ? state.params.stressDrop : state.params.stress_drop;
        if (stress !== undefined) this.stressDrop.set(Math.round(stress * 100));
      }
      if (state.strategy) {
        this.selectedStrategy.set(state.strategy);
      }
      if (state.savedAt) {
        const d = new Date(state.savedAt);
        this.lastSavedDate.set(
          `${d.toLocaleDateString('pt-BR')} às ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
        );
      }
      return true;
    }
    return false;
  }

  private loadPredictionFromCache(): boolean {
    try {
      const raw = localStorage.getItem(this.CACHE_KEY);
      if (!raw) return false;
      const state = JSON.parse(raw);
      return this.applyPredictionState(state);
    } catch (e) {
      console.warn('Erro ao restaurar previsão do cache:', e);
    }
    return false;
  }
}


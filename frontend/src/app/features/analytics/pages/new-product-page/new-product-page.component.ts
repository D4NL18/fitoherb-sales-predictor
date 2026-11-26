/**
 * Página inteligente da feature Viabilidade de Produto Novo (/analytics/produto-novo, F2).
 * Coordena o Workbench Assimétrico, NewProductStore, estados interativos (1..8),
 * região aria-live="polite" e [attr.inert] quando o Drawer de explicabilidade está aberto.
 */
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { ErrorBannerComponent } from '../../components/error-banner/error-banner.component';
import { ResultStateComponent } from '../../components/result-state/result-state.component';
import { NewProductForecastRequest, SimilarProductItem } from '../../models/new-product.model';
import { PtDatePipe } from '../../pipes/pt-br-format.pipes';
import { NewProductStore } from '../../services/new-product.store';
import {
  NEW_PRODUCT_OPTIONS_GENERIC_ERROR_MESSAGE,
  resolveNewProductErrorMessage,
} from '../../utils/analytics-error';
import { ResultStateAction, ResultStateView } from '../../utils/cross-sell-view';
import { formatDecimal } from '../../utils/pt-br-format';
import { NewProductFormComponent } from './components/new-product-form/new-product-form.component';
import { NewProductResultsComponent } from './components/new-product-results/new-product-results.component';
import { NewProductSimilarsDrawerComponent } from './components/new-product-similars-drawer/new-product-similars-drawer.component';

const INITIAL_RESULT_STATE: ResultStateView = {
  icon: 'document',
  title: 'Simule um lançamento sem precisar de SKU',
  text: 'Selecione o Fornecedor, descreva o produto e informe o preço previsto. O sistema busca lançamentos realmente similares pela descrição, faixa de preço e fornecedor.',
  actionLabel: 'Selecionar Fornecedor',
  action: 'focus-field',
  tone: 'neutral',
};

const EMPTY_CATALOG_STATE: ResultStateView = {
  icon: 'box',
  title: 'Nenhuma opção ativa disponível no catálogo',
  text: 'Não há tipos ou fornecedores ativos elegíveis no momento para simular um novo lançamento.',
  actionLabel: 'Recarregar catálogo',
  action: 'retry',
  tone: 'neutral',
};

@Component({
  selector: 'app-new-product-page',
  standalone: true,
  imports: [
    ErrorBannerComponent,
    ResultStateComponent,
    PtDatePipe,
    NewProductFormComponent,
    NewProductResultsComponent,
    NewProductSimilarsDrawerComponent,
  ],
  providers: [NewProductStore],
  templateUrl: './new-product-page.component.html',
  styleUrl: './new-product-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProductPageComponent implements OnInit {
  protected readonly store = inject(NewProductStore);

  private readonly formComponent = viewChild(NewProductFormComponent);

  protected readonly drawerReturnFocusTo = signal<HTMLElement | null>(null);
  protected readonly customLiveAnnouncement = signal<string>('');

  protected readonly initialStateView = INITIAL_RESULT_STATE;
  protected readonly emptyCatalogStateView = EMPTY_CATALOG_STATE;

  protected readonly optionsErrorMessage = computed(() => {
    if (this.store.optionsState() !== 'error') return null;
    return resolveNewProductErrorMessage(
      this.store.optionsError(),
      NEW_PRODUCT_OPTIONS_GENERIC_ERROR_MESSAGE,
    );
  });

  protected readonly forecastErrorMessage = computed(() => {
    if (this.store.simulationState() !== 'error') return '';
    return resolveNewProductErrorMessage(this.store.forecastError());
  });

  protected readonly insufficientDataView = computed<ResultStateView>(() => {
    const apiMsg = this.store.forecastError()?.message?.trim();
    const baseMsg = apiMsg || 'Base de lançamentos similares insuficiente para o tipo selecionado.';
    return {
      icon: 'chart',
      title: 'Base histórica insuficiente neste Tipo',
      text: `${baseMsg} É necessário haver ao menos 3 lançamentos recentes (desde 01/04/2025 com mínimo de 3 meses de histórico).`,
      actionLabel: 'Escolher outro Tipo',
      action: 'focus-field',
      tone: 'warning',
    };
  });

  protected readonly liveAnnouncement = computed(() => {
    const custom = this.customLiveAnnouncement();
    if (custom) return custom;

    const simState = this.store.simulationState();
    if (simState === 'loading') {
      return 'Calculando projeção conservadora de produto novo.';
    }
    if (simState === 'success') {
      const data = this.store.forecastData();
      if (!data) return '';
      const qty = formatDecimal(data.aggregatedTotals.totalQuantity, 0);
      const parecer = data.financialViability.parecer ?? 'Simulação concluída.';
      return `Simulação concluída: ${qty} unidades conservadoras. ${parecer}`;
    }
    if (simState === 'insufficient') {
      return 'Base histórica insuficiente neste Tipo. Selecione outro tipo de produto.';
    }
    if (simState === 'error') {
      return 'Não foi possível concluir a simulação agora.';
    }
    return '';
  });

  ngOnInit(): void {
    this.store.loadOptions();
  }

  protected onSubmitForecast(request: NewProductForecastRequest): void {
    this.customLiveAnnouncement.set('');
    this.store.simulate(request);
  }

  protected onResetSimulation(): void {
    this.store.reset();
    this.customLiveAnnouncement.set('Simulação limpa.');
  }

  protected onFormChanged(): void {
    this.customLiveAnnouncement.set('');
    this.store.markDirty();
  }

  protected onResultStateAction(action: ResultStateAction): void {
    if (action === 'focus-field') {
      this.formComponent()?.focusTipoSelect();
      return;
    }
    if (action === 'retry') {
      this.store.loadOptions();
    }
  }

  protected onExplainSimilar(payload: {
    similar: SimilarProductItem;
    trigger: HTMLElement | null;
  }): void {
    this.drawerReturnFocusTo.set(payload.trigger);
    this.store.openSimilar(payload.similar);
  }

  protected onCloseDrawer(): void {
    this.store.closeSimilar();
  }
}

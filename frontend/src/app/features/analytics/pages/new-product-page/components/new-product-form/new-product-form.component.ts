/**
 * Formulário sem SKU para simulação de Viabilidade de Produto Novo (F2, P-140 a P-142).
 * Dumb component (OnPush + Signals Angular 18): validação inline pt-BR, combobox ARIA de fornecedor,
 * skeleton de `/options` e proteção anti-double-submit.
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { ErrorBannerComponent } from '../../../../components/error-banner/error-banner.component';
import {
  NewProductApiError,
  NewProductForecastRequest,
  NewProductOptions,
} from '../../../../models/new-product.model';
import { NewProductFormField, resolveNewProductFieldError } from '../../../../utils/analytics-error';
import { formatDecimal, parsePtBrNumber } from '../../../../utils/pt-br-format';

function normalizeSearch(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

const HORIZON_OPTIONS = [
  { value: 1, label: '1 mês' },
  { value: 2, label: '2 meses' },
  { value: 3, label: '3 meses' },
] as const;

const MIN_DESC_LEN = 3;
const MAX_DESC_LEN = 120;
const MAX_MARGIN_PCT = 100;

@Component({
  selector: 'app-new-product-form',
  standalone: true,
  imports: [ErrorBannerComponent],
  templateUrl: './new-product-form.component.html',
  styleUrl: './new-product-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProductFormComponent {
  readonly options = input<NewProductOptions | null>(null);
  readonly optionsLoading = input<boolean>(false);
  readonly optionsError = input<NewProductApiError | null>(null);
  readonly optionsErrorBannerMessage = input<string | null>(null);
  readonly hasEmptyCatalog = input<boolean>(false);
  readonly submitting = input<boolean>(false);
  readonly apiError = input<NewProductApiError | null>(null);

  readonly submitForecast = output<NewProductForecastRequest>();
  readonly resetSimulation = output<void>();
  readonly formChanged = output<void>();
  readonly retryOptions = output<void>();

  private readonly fornecedorInput = viewChild<ElementRef<HTMLInputElement>>('fornecedorInput');
  private readonly descricaoInput = viewChild<ElementRef<HTMLInputElement>>('descricaoInput');
  private readonly precoInput = viewChild<ElementRef<HTMLInputElement>>('precoInput');
  private readonly custoInput = viewChild<ElementRef<HTMLInputElement>>('custoInput');
  private readonly margemInput = viewChild<ElementRef<HTMLInputElement>>('margemInput');

  protected readonly horizonOptions = HORIZON_OPTIONS;
  protected readonly maxDescLen = MAX_DESC_LEN;

  protected readonly fornecedorQuery = signal<string>('');
  protected readonly fornecedorDropdownOpen = signal<boolean>(false);
  protected readonly activeFornecedorIndex = signal<number>(-1);
  protected readonly descricao = signal<string>('');
  protected readonly precoRaw = signal<string>('');
  protected readonly custoRaw = signal<string>('');
  protected readonly margemRaw = signal<string>('');
  protected readonly horizonMonths = signal<number>(3);

  protected readonly submitted = signal<boolean>(false);
  protected readonly touched = signal<Record<NewProductFormField, boolean>>({
    tipo: false,
    fornecedor: false,
    descricao: false,
    precoVendaPrevisto: false,
    custoUnitario: false,
    margemMinimaDesejada: false,
    horizonMonths: false,
  });

  protected readonly fornecedoresList = computed(() => this.options()?.fornecedores ?? []);

  protected readonly filteredFornecedores = computed(() => {
    const query = normalizeSearch(this.fornecedorQuery());
    const all = this.fornecedoresList();
    if (!query) return all;
    return all.filter((item) => normalizeSearch(item).includes(query));
  });

  protected readonly matchedFornecedor = computed(() => {
    const raw = this.fornecedorQuery().trim();
    if (!raw) return null;
    const exact = this.fornecedoresList().find((item) => item === raw);
    if (exact) return exact;
    const normalized = normalizeSearch(raw);
    return this.fornecedoresList().find((item) => normalizeSearch(item) === normalized) ?? null;
  });

  protected readonly descricaoLength = computed(() => this.descricao().trim().length);
  protected readonly parsedPreco = computed(() => parsePtBrNumber(this.precoRaw()));
  protected readonly parsedCusto = computed(() => parsePtBrNumber(this.custoRaw()));
  protected readonly parsedMargem = computed(() => parsePtBrNumber(this.margemRaw()));

  protected readonly fornecedorError = computed(() => {
    const apiErr = resolveNewProductFieldError(this.apiError(), 'fornecedor');
    if (apiErr) return apiErr;
    if (!this.shouldShowError('fornecedor')) return null;
    if (!this.matchedFornecedor()) {
      return 'Selecione um fornecedor ativo da lista.';
    }
    return null;
  });

  protected readonly descricaoError = computed(() => {
    const apiErr = resolveNewProductFieldError(this.apiError(), 'descricao');
    if (apiErr) return apiErr;
    if (!this.shouldShowError('descricao')) return null;
    const len = this.descricaoLength();
    if (len < MIN_DESC_LEN || len > MAX_DESC_LEN) {
      return 'A descrição deve ter entre 3 e 120 caracteres.';
    }
    return null;
  });

  protected readonly precoError = computed(() => {
    const apiErr = resolveNewProductFieldError(this.apiError(), 'precoVendaPrevisto');
    if (apiErr) return apiErr;
    if (!this.shouldShowError('precoVendaPrevisto')) return null;
    const preco = this.parsedPreco();
    if (preco === null || preco <= 0) {
      return 'Informe um preço de venda previsto maior que R$ 0,00.';
    }
    return null;
  });

  protected readonly custoError = computed(() => {
    const apiErr = resolveNewProductFieldError(this.apiError(), 'custoUnitario');
    if (apiErr) return apiErr;
    const raw = this.custoRaw().trim();
    if (!raw) return null;
    const custo = this.parsedCusto();
    const preco = this.parsedPreco();
    // Erro de custo > preço aparece imediatamente para bloquear inconsistência matemática.
    if (custo !== null && preco !== null && preco > 0 && custo > preco) {
      return 'O custo unitário não pode ser maior que o preço de venda previsto.';
    }
    if (!this.shouldShowError('custoUnitario')) return null;
    if (custo === null || custo <= 0) {
      return 'Quando informado, o custo unitário deve ser maior que R$ 0,00.';
    }
    return null;
  });

  protected readonly custoZeroMarginHint = computed(() => {
    if (this.custoError()) return null;
    const custo = this.parsedCusto();
    const preco = this.parsedPreco();
    if (custo !== null && preco !== null && preco > 0 && custo === preco) {
      return 'Com custo igual ao preço, a margem bruta prevista é 0,00%.';
    }
    return null;
  });

  protected readonly margemError = computed(() => {
    const apiErr = resolveNewProductFieldError(this.apiError(), 'margemMinimaDesejada');
    if (apiErr) return apiErr;
    const raw = this.margemRaw().trim();
    if (!raw) return null;
    if (!this.shouldShowError('margemMinimaDesejada')) return null;
    const margem = this.parsedMargem();
    if (margem === null || margem < 0 || margem > MAX_MARGIN_PCT) {
      return 'Informe uma margem mínima entre 0% e 100%.';
    }
    return null;
  });

  protected readonly margemWithoutCostHint = computed(() => {
    if (this.margemError()) return null;
    const margem = this.parsedMargem();
    const hasCost = this.custoRaw().trim().length > 0;
    if (margem !== null && !hasCost) {
      return 'Informe também o custo unitário para avaliar se esta margem mínima será atingida.';
    }
    return null;
  });

  protected readonly canSubmit = computed(
    () =>
      !this.optionsLoading() &&
      this.optionsErrorBannerMessage() === null &&
      !this.hasEmptyCatalog() &&
      !this.submitting(),
  );

  protected readonly activeDescendantId = computed(() => {
    if (!this.fornecedorDropdownOpen()) return null;
    const idx = this.activeFornecedorIndex();
    if (idx < 0 || idx >= this.filteredFornecedores().length) return null;
    return `np-fornecedor-opt-${idx}`;
  });

  focusTipoSelect(): void {
    this.fornecedorInput()?.nativeElement.focus();
  }

  protected onFornecedorInput(value: string): void {
    this.fornecedorQuery.set(value);
    this.fornecedorDropdownOpen.set(true);
    this.activeFornecedorIndex.set(0);
    this.formChanged.emit();
  }

  protected onFornecedorFocus(): void {
    if (this.optionsLoading() || this.hasEmptyCatalog()) return;
    this.fornecedorDropdownOpen.set(true);
    this.activeFornecedorIndex.set(this.filteredFornecedores().length > 0 ? 0 : -1);
  }

  protected onFornecedorBlur(): void {
    // Atraso curto permite clique/mousedown em opção antes de fechar o listbox.
    setTimeout(() => {
      this.fornecedorDropdownOpen.set(false);
      this.markTouched('fornecedor');
    }, 120);
  }

  protected onFornecedorKeydown(event: KeyboardEvent): void {
    const items = this.filteredFornecedores();
    switch (event.key) {
      case 'ArrowDown': {
        event.preventDefault();
        if (!this.fornecedorDropdownOpen()) {
          this.fornecedorDropdownOpen.set(true);
          this.activeFornecedorIndex.set(items.length > 0 ? 0 : -1);
          return;
        }
        if (items.length > 0) {
          this.activeFornecedorIndex.update((idx) => (idx + 1) % items.length);
        }
        break;
      }
      case 'ArrowUp': {
        event.preventDefault();
        if (!this.fornecedorDropdownOpen()) {
          this.fornecedorDropdownOpen.set(true);
          this.activeFornecedorIndex.set(items.length > 0 ? items.length - 1 : -1);
          return;
        }
        if (items.length > 0) {
          this.activeFornecedorIndex.update((idx) => (idx <= 0 ? items.length - 1 : idx - 1));
        }
        break;
      }
      case 'Enter': {
        if (this.fornecedorDropdownOpen()) {
          const idx = this.activeFornecedorIndex();
          if (idx >= 0 && idx < items.length) {
            event.preventDefault();
            this.selectFornecedor(items[idx]);
          }
        }
        break;
      }
      case 'Escape': {
        if (this.fornecedorDropdownOpen()) {
          event.preventDefault();
          this.fornecedorDropdownOpen.set(false);
        }
        break;
      }
    }
  }

  protected selectFornecedor(value: string): void {
    this.fornecedorQuery.set(value);
    this.fornecedorDropdownOpen.set(false);
    this.activeFornecedorIndex.set(-1);
    this.markTouched('fornecedor');
    this.formChanged.emit();
  }

  protected clearFornecedor(): void {
    this.fornecedorQuery.set('');
    this.fornecedorDropdownOpen.set(true);
    this.activeFornecedorIndex.set(0);
    this.markTouched('fornecedor');
    this.formChanged.emit();
    this.fornecedorInput()?.nativeElement.focus();
  }

  protected onDescricaoChange(value: string): void {
    this.descricao.set(value);
    this.formChanged.emit();
  }

  protected onPrecoChange(value: string): void {
    this.precoRaw.set(value);
    this.formChanged.emit();
  }

  protected onPrecoBlur(): void {
    this.markTouched('precoVendaPrevisto');
    const parsed = this.parsedPreco();
    if (parsed !== null && parsed > 0) {
      this.precoRaw.set(formatDecimal(parsed, 2));
    }
  }

  protected onCustoChange(value: string): void {
    this.custoRaw.set(value);
    this.formChanged.emit();
  }

  protected onCustoBlur(): void {
    this.markTouched('custoUnitario');
    const parsed = this.parsedCusto();
    if (parsed !== null && parsed > 0) {
      this.custoRaw.set(formatDecimal(parsed, 2));
    }
  }

  protected onMargemChange(value: string): void {
    this.margemRaw.set(value);
    this.formChanged.emit();
  }

  protected onMargemBlur(): void {
    this.markTouched('margemMinimaDesejada');
    const parsed = this.parsedMargem();
    if (parsed !== null && parsed >= 0 && parsed <= MAX_MARGIN_PCT) {
      this.margemRaw.set(formatDecimal(parsed, 1));
    }
  }

  protected onHorizonChange(value: number): void {
    this.horizonMonths.set(value);
    this.formChanged.emit();
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    if (!this.canSubmit()) return;

    this.submitted.set(true);
    this.fornecedorDropdownOpen.set(false);

    if (!this.isFormValid()) {
      this.focusFirstInvalidField();
      return;
    }

    const preco = this.parsedPreco();
    const fornecedor = this.matchedFornecedor();
    if (preco === null || !fornecedor) return;

    const custo = this.custoRaw().trim() ? this.parsedCusto() : null;
    const margemPct = this.margemRaw().trim() ? this.parsedMargem() : null;
    const margemDecimal =
      margemPct !== null ? Number((margemPct / MAX_MARGIN_PCT).toFixed(4)) : null;

    this.submitForecast.emit({
      tipo: null,
      fornecedor,
      descricao: this.descricao().trim(),
      precoVendaPrevisto: Number(preco.toFixed(2)),
      custoUnitario: custo !== null ? Number(custo.toFixed(2)) : null,
      margemMinimaDesejada: margemDecimal,
      horizonMonths: this.horizonMonths(),
    });
  }

  protected onReset(): void {
    this.fornecedorQuery.set('');
    this.fornecedorDropdownOpen.set(false);
    this.activeFornecedorIndex.set(-1);
    this.descricao.set('');
    this.precoRaw.set('');
    this.custoRaw.set('');
    this.margemRaw.set('');
    this.horizonMonths.set(3);
    this.submitted.set(false);
    this.touched.set({
      tipo: false,
      fornecedor: false,
      descricao: false,
      precoVendaPrevisto: false,
      custoUnitario: false,
      margemMinimaDesejada: false,
      horizonMonths: false,
    });
    this.resetSimulation.emit();
    this.focusTipoSelect();
  }

  protected markTouched(field: NewProductFormField): void {
    this.touched.update((prev) => ({ ...prev, [field]: true }));
  }

  private shouldShowError(field: NewProductFormField): boolean {
    return this.submitted() || this.touched()[field];
  }

  private isFormValid(): boolean {
    return (
      !this.fornecedorError() &&
      !this.descricaoError() &&
      !this.precoError() &&
      !this.custoError() &&
      !this.margemError()
    );
  }

  private focusFirstInvalidField(): void {
    if (this.fornecedorError()) {
      this.fornecedorInput()?.nativeElement.focus();
      return;
    }
    if (this.descricaoError()) {
      this.descricaoInput()?.nativeElement.focus();
      return;
    }
    if (this.precoError()) {
      this.precoInput()?.nativeElement.focus();
      return;
    }
    if (this.custoError()) {
      this.custoInput()?.nativeElement.focus();
      return;
    }
    if (this.margemError()) {
      this.margemInput()?.nativeElement.focus();
    }
  }
}

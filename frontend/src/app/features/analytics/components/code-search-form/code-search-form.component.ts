/**
 * Formulário de consulta por código, reutilizado nos dois modos (Design Plan §5.4, §6.4; F-09, F-10, F-12).
 * Burro: valida só o formato (dígitos, > 0) e emite o código. Com `enableProductSearch` vira combobox
 * acessível (D-7, contrato §3.6): busca por código ou descrição com debounce, mínimo de caracteres,
 * setas/Enter/Escape; selecionar uma opção preenche o SKU no campo.
 * Enviar, escolher, limpar ou sair do campo cancelam a busca pendente e a em voo, para a lista não
 * reabrir durante o carregamento (UX B-1).
 */
import {
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, map, of, switchMap, timer } from 'rxjs';
import { AnalyticsService } from '../../services/analytics.service';
import { ConsultedProduct } from '../../models/cross-sell.model';
import { ANALYTICS_ERROR_MESSAGES } from '../../utils/analytics-error';

/** Espera após a última tecla antes de consultar a busca de produto (T-18). */
export const PRODUCT_SEARCH_DEBOUNCE_MS = 300;
/** Mínimo de caracteres para consultar a busca de produto (contrato §3.6). */
export const PRODUCT_SEARCH_MIN_CHARS = 2;
/** Quantidade de sugestões pedidas ao backend (limite do contrato §3.6). */
export const PRODUCT_SEARCH_LIMIT = 20;
/** Código válido: inteiro positivo sem zero à esquerda (P-067, evita XSL-004). */
const POSITIVE_CODE_PATTERN = /^[1-9]\d*$/;
const NO_ACTIVE_OPTION = -1;
const SINGLE_OPTION = 1;

/** Resultado de uma busca de produto, com o termo que a originou. */
interface ProductSearchResult {
  query: string;
  options: ConsultedProduct[];
}

let nextFormId = 0;

@Component({
  selector: 'app-code-search-form',
  standalone: true,
  templateUrl: './code-search-form.component.html',
  styleUrl: './code-search-form.component.scss',
})
export class CodeSearchFormComponent {
  private readonly analyticsService = inject(AnalyticsService);
  private readonly inputRef = viewChild.required<ElementRef<HTMLInputElement>>('codeInput');
  /** Termos digitados; `null` cancela a busca pendente e a em voo. */
  private readonly queries = new Subject<string | null>();
  /** Último código enviado: Enter repetido no mesmo código durante o carregamento é ignorado (NB-1). */
  private lastSubmittedCode: number | null = null;

  readonly label = input.required<string>();
  readonly hint = input<string>('');
  readonly placeholder = input<string>('');
  readonly submitLabel = input.required<string>();
  readonly loading = input<boolean>(false);
  /** Erro vindo da API (XSL-001/002/004), já traduzido para a tela. */
  readonly fieldError = input<string | null>(null);
  readonly initialValue = input<string>('');
  readonly enableProductSearch = input<boolean>(false);
  /** Mensagem da validação local de formato (o modo produto orienta a escolher da lista, B-3). */
  readonly invalidFormatMessage = input<string>(ANALYTICS_ERROR_MESSAGES['XSL-004']);
  readonly search = output<number>();

  protected readonly ids = createIds();
  protected readonly value = signal('');
  protected readonly localError = signal<string | null>(null);
  protected readonly editedSinceError = signal(false);
  protected readonly suggestions = signal<ConsultedProduct[]>([]);
  protected readonly listOpen = signal(false);
  protected readonly activeIndex = signal(NO_ACTIVE_OPTION);
  /** Termo da última busca sem resultado, para o aviso "Nenhum produto encontrado" (B-3). */
  protected readonly noResultsTerm = signal<string | null>(null);

  protected readonly displayedError = computed(
    () => this.localError() ?? (this.editedSinceError() ? null : this.fieldError()),
  );
  protected readonly expanded = computed(
    () => this.listOpen() && this.suggestions().length > 0 && !this.loading(),
  );
  protected readonly activeOptionId = computed(() =>
    this.expanded() && this.activeIndex() >= 0 ? this.optionId(this.activeIndex()) : null,
  );
  protected readonly searchStatus = computed(() => {
    const term = this.noResultsTerm();
    return term === null || this.loading() ? '' : `Nenhum produto encontrado para "${term}".`;
  });

  constructor() {
    this.listenProductSearch();
    effect(() => {
      const initial = this.initialValue();
      untracked(() => {
        this.value.set(initial);
        this.lastSubmittedCode = POSITIVE_CODE_PATTERN.test(initial) ? Number(initial) : null;
      });
    }, { allowSignalWrites: true });
    effect(() => {
      this.fieldError();
      untracked(() => this.editedSinceError.set(false));
    }, { allowSignalWrites: true });
  }

  /** Foca o campo (ação "Ir para o campo" do estado inicial). */
  focus(): void {
    this.inputRef().nativeElement.focus();
  }

  /** Limpa e foca o campo ("Buscar outro produto", "Consultar outro cliente", botão ×). */
  clearAndFocus(): void {
    this.value.set('');
    this.localError.set(null);
    this.cancelSearch();
    this.focus();
  }

  protected optionId(index: number): string {
    return `${this.ids.listbox}-option-${index}`;
  }

  protected onInput(event: Event): void {
    const typed = (event.target as HTMLInputElement).value;
    this.value.set(typed);
    this.localError.set(null);
    this.editedSinceError.set(true);
    this.noResultsTerm.set(null);
    if (this.enableProductSearch()) this.queries.next(typed.trim());
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.cancelSearch();
    const code = this.value().trim();
    if (!POSITIVE_CODE_PATTERN.test(code)) {
      this.localError.set(this.invalidFormatMessage());
      this.focus();
      return;
    }
    const parsed = Number(code);
    if (this.loading() && parsed === this.lastSubmittedCode) return;
    this.localError.set(null);
    this.editedSinceError.set(false);
    this.lastSubmittedCode = parsed;
    this.search.emit(parsed);
  }

  protected onKeydown(event: KeyboardEvent): void {
    if (!this.expanded()) return;
    const handlers: Record<string, () => void> = {
      ArrowDown: () => this.moveActive(1),
      ArrowUp: () => this.moveActive(-1),
      Enter: () => this.selectActive(),
      Escape: () => this.cancelSearch(),
    };
    const handler = handlers[event.key];
    if (!handler) return;
    if (event.key === 'Enter' && !this.canSelectOnEnter()) return;
    event.preventDefault();
    handler();
  }

  protected onBlur(): void {
    this.cancelSearch();
  }

  protected selectOption(option: ConsultedProduct): void {
    this.value.set(String(option.codigo));
    this.localError.set(null);
    this.cancelSearch();
  }

  /** Cancela a busca pendente/em voo e fecha a lista e o aviso de "nenhum produto". */
  private cancelSearch(): void {
    this.queries.next(null);
    this.listOpen.set(false);
    this.activeIndex.set(NO_ACTIVE_OPTION);
    this.noResultsTerm.set(null);
  }

  /** Enter seleciona a opção ativa ou, sem opção ativa, a única opção da lista (B-3). */
  private canSelectOnEnter(): boolean {
    return this.activeIndex() >= 0 || this.suggestions().length === SINGLE_OPTION;
  }

  private moveActive(step: number): void {
    const count = this.suggestions().length;
    const next = this.activeIndex() + step;
    this.activeIndex.set(Math.min(Math.max(next, 0), count - 1));
  }

  private selectActive(): void {
    const option = this.suggestions()[Math.max(this.activeIndex(), 0)];
    if (option) this.selectOption(option);
  }

  private listenProductSearch(): void {
    this.queries
      .pipe(
        switchMap((query) => (query === null ? EMPTY : this.debouncedSearch(query))),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((result) => this.showResult(result));
  }

  private debouncedSearch(query: string): Observable<ProductSearchResult> {
    return timer(PRODUCT_SEARCH_DEBOUNCE_MS).pipe(
      switchMap(() => (this.shouldSearch(query) ? this.fetchOptions(query) : EMPTY)),
    );
  }

  private fetchOptions(query: string): Observable<ProductSearchResult> {
    return this.analyticsService.searchProducts(query, { limit: PRODUCT_SEARCH_LIMIT, offset: 0 }).pipe(
      map((response) => ({ query, options: response.data })),
      catchError(() => of<ProductSearchResult>({ query, options: [] })),
    );
  }

  /** Só abre a lista se o termo ainda é o do campo, o campo está focado e nada está carregando. */
  private showResult(result: ProductSearchResult): void {
    if (!this.isStillRelevant(result.query)) return;
    this.suggestions.set(result.options);
    this.activeIndex.set(NO_ACTIVE_OPTION);
    this.listOpen.set(result.options.length > 0);
    this.noResultsTerm.set(result.options.length === 0 ? result.query : null);
  }

  private isStillRelevant(query: string): boolean {
    const field = this.inputRef().nativeElement;
    return query === this.value().trim() && field.ownerDocument.activeElement === field && !this.loading();
  }

  private shouldSearch(query: string): boolean {
    if (query.length >= PRODUCT_SEARCH_MIN_CHARS) return this.enableProductSearch();
    this.listOpen.set(false);
    this.activeIndex.set(NO_ACTIVE_OPTION);
    return false;
  }
}

function createIds(): { input: string; hint: string; error: string; listbox: string } {
  const prefix = `xs-code-${nextFormId++}`;
  return { input: `${prefix}-input`, hint: `${prefix}-hint`, error: `${prefix}-error`, listbox: `${prefix}-listbox` };
}

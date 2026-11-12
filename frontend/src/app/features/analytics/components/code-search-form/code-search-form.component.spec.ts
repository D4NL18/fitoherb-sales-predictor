/**
 * T-18 — Combobox de busca de produto (F-12; contrato §3.6; Design Plan D-7, §5.4).
 *
 * Interface esperada de `CodeSearchFormComponent` (burro, reutilizado nos dois modos):
 * inputs `label`, `hint`, `submitLabel`, `loading`, `fieldError`, `initialValue` e
 * `enableProductSearch` (true só no modo produto); output `search` (inteiro positivo).
 * Com `enableProductSearch`, o input tem `role="combobox"` e consulta `AnalyticsService.searchProducts`
 * com debounce de 300 ms a partir de 2 caracteres; a lista usa `role="listbox"`/`role="option"`.
 * Etapa 4 (UX B-1, B-3, NB-1): a lista não reabre durante o carregamento, a validação do modo produto
 * orienta a escolher da lista, busca sem resultado é anunciada e Enter durante o loading com outro código envia.
 */
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { Subject, of } from 'rxjs';
import { CodeSearchFormComponent } from './code-search-form.component';
import { AnalyticsService } from '../../services/analytics.service';
import { searchResponse } from '../../testing/cross-sell-test-data';
import { PRODUCT_INVALID_FORMAT_MESSAGE } from '../../utils/analytics-error';
import { ProductSearchResponse } from '../../models/cross-sell.model';

const DEBOUNCE_MS = 300;

describe('CodeSearchFormComponent (combobox de produto)', () => {
  let fixture: ComponentFixture<CodeSearchFormComponent>;
  let element: HTMLElement;
  let service: jasmine.SpyObj<AnalyticsService>;
  let emitted: number[];

  beforeEach(async () => {
    service = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', ['searchProducts']);
    service.searchProducts.and.returnValue(of(searchResponse()));
    await TestBed.configureTestingModule({
      imports: [CodeSearchFormComponent],
      providers: [{ provide: AnalyticsService, useValue: service }],
    }).compileComponents();
    fixture = TestBed.createComponent(CodeSearchFormComponent);
    fixture.componentRef.setInput('label', 'Produto (código ou descrição)');
    fixture.componentRef.setInput('invalidFormatMessage', PRODUCT_INVALID_FORMAT_MESSAGE);
    fixture.componentRef.setInput('hint', 'Use o código do catálogo (o mesmo da tabela de preços).');
    fixture.componentRef.setInput('submitLabel', 'Ver sugestões');
    fixture.componentRef.setInput('enableProductSearch', true);
    emitted = [];
    fixture.componentInstance.search.subscribe((value: number) => emitted.push(value));
    element = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  function input(): HTMLInputElement {
    return element.querySelector('input') as HTMLInputElement;
  }

  function type(value: string): void {
    input().focus();
    input().value = value;
    input().dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function press(key: string): void {
    input().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    fixture.detectChanges();
  }

  function submit(): void {
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  function setLoading(loading: boolean): void {
    fixture.componentRef.setInput('loading', loading);
    fixture.detectChanges();
  }

  function options(): HTMLElement[] {
    return Array.from(element.querySelectorAll('[role="option"]')) as HTMLElement[];
  }

  it('o campo é um combobox acessível com label visível', () => {
    expect(input().getAttribute('role')).toBe('combobox');
    expect(input().getAttribute('aria-expanded')).toBe('false');
    const label = element.querySelector(`label[for="${input().id}"]`);
    expect(label?.textContent).toContain('Produto (código ou descrição)');
  });

  it('espera 300 ms de debounce antes de buscar', fakeAsync(() => {
    type('ch');
    tick(DEBOUNCE_MS - 1);
    expect(service.searchProducts).not.toHaveBeenCalled();

    tick(1);
    expect(service.searchProducts).toHaveBeenCalledOnceWith('ch', { limit: 20, offset: 0 });
  }));

  it('não busca com menos de 2 caracteres', fakeAsync(() => {
    type('c');
    tick(DEBOUNCE_MS * 2);
    expect(service.searchProducts).not.toHaveBeenCalled();
  }));

  it('digitação rápida gera uma única busca com o último termo', fakeAsync(() => {
    type('ch');
    tick(100);
    type('cha');
    tick(100);
    type('cha v');
    tick(DEBOUNCE_MS);

    expect(service.searchProducts).toHaveBeenCalledTimes(1);
    expect(service.searchProducts.calls.mostRecent().args[0]).toBe('cha v');
  }));

  it('mostra as opções e navega pelo teclado', fakeAsync(() => {
    type('cha');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    expect(input().getAttribute('aria-expanded')).toBe('true');
    expect(element.querySelector('[role="listbox"]')).not.toBeNull();
    expect(options().length).toBe(2);
    expect(options()[0].textContent).toContain('CHA VERDE 100G');

    press('ArrowDown');
    expect(options()[0].getAttribute('aria-selected')).toBe('true');
    expect(input().getAttribute('aria-activedescendant')).toBe(options()[0].id);

    press('ArrowDown');
    expect(options()[1].getAttribute('aria-selected')).toBe('true');

    press('ArrowUp');
    expect(options()[0].getAttribute('aria-selected')).toBe('true');
  }));

  it('Enter na opção ativa preenche o SKU e fecha a lista', fakeAsync(() => {
    type('cha');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    press('ArrowDown');
    press('ArrowDown');
    press('Enter');

    expect(input().value).toBe('1002');
    expect(input().getAttribute('aria-expanded')).toBe('false');
  }));

  it('clique na opção preenche o SKU', fakeAsync(() => {
    type('cha');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    options()[0].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    options()[0].click();
    fixture.detectChanges();

    expect(input().value).toBe('1001');
  }));

  it('Escape fecha a lista sem alterar o valor digitado', fakeAsync(() => {
    type('cha');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    press('Escape');

    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(input().value).toBe('cha');
  }));

  it('envio só com código numérico positivo', () => {
    type('1001');
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    expect(emitted).toEqual([1001]);
  });

  it('envio com texto livre mostra a validação e não emite', () => {
    type('cha verde');
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(emitted).toEqual([]);
    expect(element.textContent).toContain('Escolha um produto da lista ou digite o código (só números).');
    expect(element.textContent).not.toContain('Digite só números, sem pontos ou letras.');
  });

  it('XSL-004 vindo da API mantém a mensagem original no modo produto', () => {
    fixture.componentRef.setInput('fieldError', 'Digite só números, sem pontos ou letras.');
    fixture.detectChanges();
    expect(element.textContent).toContain('Digite só números, sem pontos ou letras.');
  });

  it('enviar fecha e mantém fechada a lista mesmo se a busca pendente responder depois (B-1)', fakeAsync(() => {
    type('1001');
    submit();
    setLoading(true);
    tick(DEBOUNCE_MS * 2);
    fixture.detectChanges();

    expect(emitted).toEqual([1001]);
    expect(service.searchProducts).not.toHaveBeenCalled();
    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(options().length).toBe(0);
  }));

  it('enviar fecha e mantém fechada a lista mesmo se a busca em voo responder depois (B-1)', fakeAsync(() => {
    const pending = new Subject<ProductSearchResponse>();
    service.searchProducts.and.returnValue(pending.asObservable());
    type('1001');
    tick(DEBOUNCE_MS);
    expect(service.searchProducts).toHaveBeenCalledTimes(1);

    submit();
    setLoading(true);
    pending.next(searchResponse());
    fixture.detectChanges();

    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(options().length).toBe(0);
    expect(element.textContent).not.toContain('Nenhum produto encontrado');
  }));

  it('lista não abre enquanto carrega, mesmo com opções já carregadas (B-1)', fakeAsync(() => {
    type('cha');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();
    expect(input().getAttribute('aria-expanded')).toBe('true');

    setLoading(true);
    expect(input().getAttribute('aria-expanded')).toBe('false');
  }));

  it('busca sem resultado anuncia "Nenhum produto encontrado" em role=status (B-3)', fakeAsync(() => {
    service.searchProducts.and.returnValue(of({ ...searchResponse(), data: [] }));
    type('xyz');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    const status = element.querySelector('[role="status"]');
    expect(status?.textContent).toContain('Nenhum produto encontrado para "xyz".');
    expect(input().getAttribute('aria-expanded')).toBe('false');
  }));

  it('Enter com uma única opção na lista seleciona essa opção (B-3)', fakeAsync(() => {
    const single = searchResponse();
    service.searchProducts.and.returnValue(of({ ...single, data: [single.data[0]] }));
    type('cha verde 100');
    tick(DEBOUNCE_MS);
    fixture.detectChanges();

    press('Enter');

    expect(input().value).toBe('1001');
    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(emitted).toEqual([]);
  }));

  it('Enter durante o carregamento envia quando o código é outro e ignora o mesmo código (NB-1)', () => {
    type('1001');
    submit();
    setLoading(true);

    submit();
    expect(emitted).toEqual([1001]);

    type('1002');
    submit();
    expect(emitted).toEqual([1001, 1002]);
  });

  it('sem enableProductSearch (modo cliente) não há combobox nem busca', fakeAsync(() => {
    fixture.componentRef.setInput('enableProductSearch', false);
    fixture.detectChanges();

    type('cha');
    tick(DEBOUNCE_MS * 2);

    expect(service.searchProducts).not.toHaveBeenCalled();
    expect(input().getAttribute('role')).not.toBe('combobox');
  }));

  it('Enter no campo do cliente envia a consulta (NB-1)', () => {
    fixture.componentRef.setInput('enableProductSearch', false);
    fixture.componentRef.setInput('invalidFormatMessage', 'Digite só números, sem pontos ou letras.');
    fixture.detectChanges();
    type('2316');

    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    input().dispatchEvent(enter);
    expect(enter.defaultPrevented).toBeFalse();

    (element.querySelector('form') as HTMLFormElement).requestSubmit();
    fixture.detectChanges();
    expect(emitted).toEqual([2316]);
  });
});

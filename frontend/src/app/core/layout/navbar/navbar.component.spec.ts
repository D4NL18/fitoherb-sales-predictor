/**
 * T-15 — Item "Análises de Vendas" na navbar (F-06; Design Plan §5.1, D-2 aprovado no checkpoint).
 * Mesmo padrão de nav-link com routerLinkActive, ícone SVG decorativo e title; aparece também no menu mobile.
 */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { catalogResponse } from '../../../features/analytics/testing/cross-sell-test-data';
import { NavbarComponent } from './navbar.component';

describe('NavbarComponent', () => {
  let fixture: ComponentFixture<NavbarComponent>;
  let element: HTMLElement;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NavbarComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(NavbarComponent);
    element = fixture.nativeElement as HTMLElement;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    httpMock.match('/api/v1/analytics/products').forEach((req) =>
      req.flush(catalogResponse()),
    );
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  function analyticsLink(): HTMLAnchorElement | null {
    return element.querySelector('a[href="/analytics"]');
  }

  it('mantém os itens existentes', () => {
    expect(element.querySelector('a[href="/pricing"]')).not.toBeNull();
    expect(element.querySelector('a[href="/inventory"]')).not.toBeNull();
  });

  it('exibe o item Análises de Vendas apontando para /analytics', () => {
    const link = analyticsLink();
    expect(link).not.toBeNull();
    expect(link?.textContent?.trim()).toContain('Análises de Vendas');
    expect(link?.classList).toContain('nav-link');
    expect(link?.getAttribute('title')).toBeTruthy();
    expect(link?.getAttribute('title')).not.toContain('em breve');
  });

  it('o ícone do item é decorativo', () => {
    const icon = analyticsLink()?.querySelector('svg');
    expect(icon).not.toBeNull();
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
  });

  it('o item vem depois de Estoque e Compras', () => {
    const hrefs = Array.from(element.querySelectorAll('a.nav-link')).map((link) => link.getAttribute('href'));
    expect(hrefs.indexOf('/analytics')).toBeGreaterThan(hrefs.indexOf('/inventory'));
  });

  it('continua disponível no menu mobile', () => {
    fixture.componentInstance.toggleMobileMenu();
    fixture.detectChanges();

    expect(element.querySelector('nav.mobile-open a[href="/analytics"]')).not.toBeNull();
  });

  it('exibe dinamicamente a quantidade real de produtos ativos retornada pelo catálogo', () => {
    const pill = element.querySelector('.catalog-status-pill') as HTMLElement;
    expect(pill).not.toBeNull();
    expect(pill.textContent?.replace(/\s+/g, ' ').trim()).toBe('Catálogo Ativo: 4 produtos');
  });
});

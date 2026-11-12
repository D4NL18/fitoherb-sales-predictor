/**
 * T-15 — Item "Análises de Vendas" na navbar (F-06; Design Plan §5.1, D-2 aprovado no checkpoint).
 * Mesmo padrão de nav-link com routerLinkActive, ícone SVG decorativo e title; aparece também no menu mobile.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { NavbarComponent } from './navbar.component';

describe('NavbarComponent', () => {
  let fixture: ComponentFixture<NavbarComponent>;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NavbarComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(NavbarComponent);
    element = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
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
});

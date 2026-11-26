import { TestBed } from '@angular/core/testing';
import { ExternalFactorsSectionComponent } from './external-factors-section.component';
import { AiDiagnosisBlockComponent } from './ai-diagnosis-block.component';
import { externalFactor } from '../testing/external-fixtures';
import { DIAGNOSIS, aiView, makeInsight } from '../testing/insight-fixtures';
import { buildExternalFactorsView, buildRadarExternoView } from '../utils/external-factors-view';
import { RadarExterno, RadarRef } from '../models/trend-insights.model';

const RADAR: RadarRef = {
  assunto: { termo: 'creatina', tipo: 'MATERIA_PRIMA' }, mesBase: '2026-10', geradoEm: '2026-11-20T10:00:00Z',
  diasDesdeGeracao: 6, desatualizado: false, origem: 'CACHE',
};

function render(view: ReturnType<typeof buildExternalFactorsView>) {
  TestBed.configureTestingModule({ imports: [ExternalFactorsSectionComponent] });
  const f = TestBed.createComponent(ExternalFactorsSectionComponent);
  f.componentRef.setInput('view', view);
  f.detectChanges();
  return f.nativeElement as HTMLElement;
}

describe('ExternalFactorsSectionComponent', () => {
  it('renderiza 8 itens, selo hipótese em contêiner tracejado e fonte segura', () => {
    const el = render(buildExternalFactorsView([externalFactor('CUSTO_MATERIA_PRIMA', {}), externalFactor('CLIMA_SAFRA', { status: 'SEM_EVIDENCIA', fontes: [] })], RADAR, [])!);
    expect(el.querySelectorAll('ul[aria-label="Fatores externos"] > li').length).toBe(8);
    expect(el.querySelector('.ext-box')).not.toBeNull();
    expect(el.querySelector('.ext-badge')?.textContent).toContain('hipótese');
    expect(el.textContent).toContain('Sem evidência encontrada');
    expect(el.textContent).toContain('Pressão de baixa nas vendas');
    expect(el.querySelector('[aria-hidden="true"]')?.textContent).toContain('▼');
    const a = el.querySelector('a') as HTMLAnchorElement;
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('title')).toBe('Data informada pela IA, não confirmada na página');
    expect(el.textContent).toContain('14/07/2026');
  });

  it('texto da IA é texto puro, nunca HTML', () => {
    const el = render(buildExternalFactorsView([externalFactor('CUSTO_MATERIA_PRIMA', { nota: '<img src=x onerror=alert(1)>' })], RADAR, [])!);
    expect(el.querySelector('img')).toBeNull();
    expect(el.textContent).toContain('<img src=x');
  });

  it('fonte sem data e url não http não vira link', () => {
    const f = externalFactor('CUSTO_MATERIA_PRIMA', {});
    f.fontes = [{ ...f.fontes[0], url: 'javascript:alert(1)', dataPublicacao: null, origemData: 'SEM_DATA' }];
    const el = render(buildExternalFactorsView([f], RADAR, [])!);
    expect(el.querySelector('a')).toBeNull();
    expect(el.textContent).toContain('sem data de publicação');
  });

  it('radar desatualizado mostra aviso em role=status; idade visível', () => {
    const el = render(buildExternalFactorsView([], { ...RADAR, desatualizado: true, diasDesdeGeracao: 40 }, ['RADAR_DESATUALIZADO'])!);
    expect(el.querySelector('[data-testid="external-stale"]')?.getAttribute('role')).toBe('status');
    expect(el.querySelector('[data-testid="external-age"]')?.textContent).toContain('há 40 dias');
  });

  it('radar indisponível é bloco neutro, sem role alert, com as 8 dimensões em details fechado', () => {
    const el = render(buildExternalFactorsView([], null, ['SEM_RADAR_EXTERNO'])!);
    expect(el.textContent).toContain('Fatores externos não avaliados nesta análise.');
    expect(el.querySelector('[role="alert"]')).toBeNull();
    const d = el.querySelector('details') as HTMLDetailsElement;
    expect(d.open).toBe(false);
    expect(d.querySelectorAll('li').length).toBe(8);
  });

  it('radar externo sem IA: movimento e intensidade, sem direção nem confiança', () => {
    const radar: RadarExterno = {
      assunto: RADAR.assunto, mesBase: '2026-10', geradoEm: RADAR.geradoEm, diasDesdeGeracao: 6, desatualizado: false,
      dimensoes: [{ dimensao: 'CLIMA_SAFRA', status: 'AVALIADA', movimento: 'CAIU', intensidade: 'FRACA', tema: null, notaRadar: 'Nota fixa.', fontes: [] }],
    };
    TestBed.configureTestingModule({ imports: [ExternalFactorsSectionComponent] });
    const f = TestBed.createComponent(ExternalFactorsSectionComponent);
    f.componentRef.setInput('radar', buildRadarExternoView(radar, []));
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Radar externo de 6 dias (sem análise de IA para este produto)');
    expect(el.textContent).toContain('Caiu · Intensidade fraca');
    expect(el.textContent).not.toContain('Confiança');
    expect(el.textContent).not.toContain('Pressão');
  });
});

describe('AiDiagnosisBlockComponent com fatores externos', () => {
  it('exibe a seção antes das hipóteses e esconde em respostas 1.1.x', () => {
    TestBed.configureTestingModule({ imports: [AiDiagnosisBlockComponent] });
    const withExt = makeInsight({ diagnosticoIa: { ...DIAGNOSIS, fatoresExternos: [externalFactor('CLIMA_SAFRA', {})], radar: RADAR } });
    let f = TestBed.createComponent(AiDiagnosisBlockComponent);
    f.componentRef.setInput('view', aiView(withExt, undefined, { diagnosticoSalvo: true }));
    f.detectChanges();
    let el = f.nativeElement as HTMLElement;
    const ext = el.querySelector('[data-testid="external-factors"]')!;
    const hyp = el.querySelector('[data-testid="ai-hipoteses"]')!;
    expect(ext).not.toBeNull();
    expect(ext.compareDocumentPosition(hyp) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    f = TestBed.createComponent(AiDiagnosisBlockComponent);
    f.componentRef.setInput('view', aiView(makeInsight({ diagnosticoIa: DIAGNOSIS }), undefined, { diagnosticoSalvo: true }));
    f.detectChanges();
    el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="external-factors"]')).toBeNull();
  });
});

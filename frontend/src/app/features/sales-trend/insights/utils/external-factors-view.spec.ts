import { ExternalFactor, RadarExterno, RadarRef } from '../models/trend-insights.model';
import { externalFactor } from '../testing/external-fixtures';
import { EXTERNAL_DIMENSIONS, buildExternalFactorsView, buildRadarExternoView } from './external-factors-view';

function row(factors: ExternalFactor[], dim: ExternalFactor['dimensao'], radar: RadarRef | null = null, avisos: string[] = []) {
  return buildExternalFactorsView(factors, radar, avisos)!.rows.find((x) => x.dimension === dim)!;
}

describe('buildExternalFactorsView', () => {
  it('sempre devolve 8 linhas na ordem fixa, mesmo sem evidência', () => {
    const v = buildExternalFactorsView([], null, [])!;
    expect(v.rows.map((r) => r.dimension)).toEqual([...EXTERNAL_DIMENSIONS]);
  });

  it('retorna null em resposta 1.1.x (sem fatoresExternos)', () => {
    expect(buildExternalFactorsView(undefined, undefined, [])).toBeNull();
  });

  it('conta só dimensões avaliadas no título', () => {
    const v = buildExternalFactorsView([externalFactor('CUSTO_MATERIA_PRIMA', {})], null, [])!;
    expect(v.title).toBe('Fatores externos (1 de 8 com evidência)');
  });

  it('SEM_EVIDENCIA mostra texto fixo sem direção, confiança ou fonte', () => {
    const r = row([externalFactor('CLIMA_SAFRA', { status: 'SEM_EVIDENCIA', direcao: 'INDETERMINADA', fontes: [] })], 'CLIMA_SAFRA');
    expect(r.statusText).toBe('Sem evidência encontrada');
    expect(r.direction).toBeNull();
    expect(r.confidenceText).toBeNull();
    expect(r.sources).toEqual([]);
  });

  it('NAO_AVALIADA traz o motivo; dimensão omitida é sintetizada', () => {
    const f = [externalFactor('CONCORRENCIA', { status: 'NAO_AVALIADA', motivoNaoAvaliado: 'SEM_TERMO_BUSCA' })];
    expect(row(f, 'CONCORRENCIA').statusText).toBe('Não avaliada');
    expect(row(f, 'CONCORRENCIA').reasonText).toBe('Não há matéria-prima ou categoria para pesquisar neste produto.');
    expect(row(f, 'EVENTOS_MERCADO').reasonText).toBe('A análise não cobriu esta dimensão.');
  });

  it('direção sempre com glifo e texto; INDETERMINADA vira "direção não exibida"', () => {
    const d = (x: ExternalFactor['direcao']) => row([externalFactor('CLIMA_SAFRA', { direcao: x })], 'CLIMA_SAFRA').direction!;
    expect(d('PRESSAO_BAIXA')).toEqual({ glyph: '▼', text: 'Pressão de baixa nas vendas', tone: 'down' });
    expect(d('PRESSAO_ALTA').glyph).toBe('▲');
    expect(d('NEUTRA').text).toBe('Sem pressão clara');
    expect(d('INDETERMINADA').text).toBe('direção não exibida');
  });

  it('confiança nunca é alta: ALTA vira baixa', () => {
    expect(row([externalFactor('CLIMA_SAFRA', { confianca: 'ALTA' })], 'CLIMA_SAFRA').confidenceText).toBe('Confiança baixa');
  });

  it('relevância em texto e NENHUMA vira linha compacta sem nota', () => {
    const r = row([externalFactor('CLIMA_SAFRA', { relevanciaAoProduto: 'NENHUMA', nota: 'x' })], 'CLIMA_SAFRA');
    expect(r.compact).toBe(true);
    expect(r.statusText).toBe('Sem relação com este produto');
    expect(r.nota).toBeNull();
    expect(row([externalFactor('CLIMA_SAFRA', { relevanciaAoProduto: 'MEDIA' })], 'CLIMA_SAFRA').relevanceText).toBe('Relevância para este produto: média');
  });

  it('selo de relação temporal', () => {
    const t = (rt: ExternalFactor['relacaoTemporal']) => row([externalFactor('CLIMA_SAFRA', { relacaoTemporal: rt })], 'CLIMA_SAFRA').temporalBadge;
    expect(t('ANTERIOR')).toBeNull();
    expect(t('CONTEMPORANEA')).toBeNull();
    expect(t('POSTERIOR')).toBe('Depois do período (só contexto)');
    expect(t('SEM_DATA')).toBe('Sem data (não vale como causa)');
    expect(t('ANTIGA')).toBe('Notícia antiga (descartada)');
  });

  it('marca dimensões promovidas a fatores', () => {
    const v = buildExternalFactorsView([externalFactor('CUSTO_MATERIA_PRIMA', {})], null, [], ['CUSTO_MATERIA_PRIMA'])!;
    expect(v.rows.find((x) => x.dimension === 'CUSTO_MATERIA_PRIMA')!.promoted).toBe(true);
    expect(v.rows.find((x) => x.dimension === 'CLIMA_SAFRA')!.promoted).toBe(false);
  });

  const radar = (over: Partial<RadarRef>): RadarRef => ({
    assunto: { termo: 'creatina', tipo: 'MATERIA_PRIMA' }, mesBase: '2026-10', geradoEm: '2026-11-20T10:00:00Z',
    diasDesdeGeracao: 6, desatualizado: false, origem: 'CACHE', ...over,
  });

  it('idade do radar: hoje, dias, cache e gerado agora', () => {
    expect(buildExternalFactorsView([], radar({}), [])!.ageText).toBe('Pesquisa sobre "creatina" · feita em 20/11/2026 (há 6 dias) · compartilhada com outros produtos');
    expect(buildExternalFactorsView([], radar({ diasDesdeGeracao: 0, origem: 'GERADO_AGORA' }), [])!.ageText).toBe('Pesquisa sobre "creatina" · feita em 20/11/2026 (hoje) · atualizada agora');
    expect(buildExternalFactorsView([], radar({ diasDesdeGeracao: 1 }), [])!.ageText).toContain('(há 1 dia)');
  });

  it('radar desatualizado: aviso e todas as linhas com confiança baixa', () => {
    const r = radar({ desatualizado: true, diasDesdeGeracao: 40 });
    const v = buildExternalFactorsView([externalFactor('CLIMA_SAFRA', { confianca: 'MEDIA' })], r, ['RADAR_DESATUALIZADO'])!;
    expect(v.staleNotice).toBe('Os fatores externos usam uma pesquisa desatualizada. Feita há 40 dias; confira as datas das fontes.');
    expect(v.rows.find((x) => x.dimension === 'CLIMA_SAFRA')!.confidenceText).toBe('Confiança baixa');
  });

  it('radar indisponível: bloco neutro, 0 de 8', () => {
    const v = buildExternalFactorsView([], null, ['SEM_RADAR_EXTERNO'])!;
    expect(v.unavailable).toEqual({ title: 'Fatores externos não avaliados nesta análise.', text: 'A análise usa só os dados de vendas e dos produtos semelhantes.' });
    expect(v.title).toBe('Fatores externos (0 de 8 com evidência)');
    expect(v.rows.every((r) => r.statusText === 'Não avaliada')).toBe(true);
  });

  it('nenhum texto exibível contém cifras, tokens ou orçamento', () => {
    const v = buildExternalFactorsView([externalFactor('CLIMA_SAFRA', {})], null, [])!;
    expect(JSON.stringify(v)).not.toMatch(/R\$|US\$|token|orçamento|dólar/i);
  });

  it('limita a 2 fontes por dimensão', () => {
    const f = externalFactor('CLIMA_SAFRA', {});
    expect(row([{ ...f, fontes: [f.fontes[0], f.fontes[0], f.fontes[0]] }], 'CLIMA_SAFRA').sources.length).toBe(2);
  });
});

describe('buildRadarExternoView', () => {
  const radar: RadarExterno = {
    assunto: { termo: 'creatina', tipo: 'MATERIA_PRIMA' }, mesBase: '2026-10', geradoEm: '2026-11-20T10:00:00Z', diasDesdeGeracao: 6, desatualizado: false,
    dimensoes: [{ dimensao: 'CLIMA_SAFRA', status: 'AVALIADA', movimento: 'SUBIU', intensidade: 'FORTE', tema: 'X', notaRadar: 'Nota fixa.', fontes: [] }],
  };

  it('título com dias, 8 linhas, movimento e intensidade em texto, sem direção sobre vendas', () => {
    const v = buildRadarExternoView(radar, [])!;
    expect(v.title).toBe('Radar externo de 6 dias (sem análise de IA para este produto)');
    expect(v.subtitle).toBe('Pesquisa geral, não específica deste produto');
    expect(v.rows.length).toBe(8);
    const r = v.rows.find((x) => x.dimension === 'CLIMA_SAFRA')!;
    expect(r.movementText).toBe('Subiu');
    expect(r.intensityText).toBe('Intensidade forte');
    expect(Object.keys(r)).not.toContain('direction');
    expect(v.rows.find((x) => x.dimension === 'CONCORRENCIA')!.statusText).toBe('Sem evidência encontrada');
  });

  it('aviso quando o radar está vencido', () => {
    expect(buildRadarExternoView({ ...radar, desatualizado: true, diasDesdeGeracao: 40 }, [])!.staleNotice).toContain('há 40 dias');
  });

  it('null sem radar', () => {
    expect(buildRadarExternoView(null, [])).toBeNull();
  });
});

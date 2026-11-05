/**
 * Suíte TDD (fase vermelha): Validação pura da Política Mín/Máx, type guard do cache v3
 * e extração amigável de mensagens de erro da API (F-07).
 *
 * Regras cobertas: P-053.3 (INV-001), A2 (INV-002), CA-06, CA-12.
 */
import { HttpErrorResponse } from '@angular/common/http';
import {
  isInventoryCachePayload,
  validateInventoryPolicy,
} from './inventory-policy.validation';
import { extractInventoryErrorMessage } from '../services/inventory.service';

describe('inventory-policy.validation (P-053.3, A2, CA-12)', () => {
  describe('validateInventoryPolicy', () => {
    it('deve aceitar a política padrão 30/60 com lead time 15 (retorna null)', () => {
      const input = { minCoverageDays: 30, maxCoverageDays: 60, leadTimeDays: 15 };
      expect(validateInventoryPolicy(input)).toBeNull();
    });

    it('deve aceitar parâmetros customizados válidos (20/45 com lead time 10)', () => {
      const input = { minCoverageDays: 20, maxCoverageDays: 45, leadTimeDays: 10 };
      expect(validateInventoryPolicy(input)).toBeNull();
    });

    it('deve retornar INV-001 quando Dias Máximo for igual a Dias Mínimo (60/60) sem mutar a entrada', () => {
      const input = Object.freeze({ minCoverageDays: 60, maxCoverageDays: 60, leadTimeDays: 15 });
      const issue = validateInventoryPolicy(input);

      expect(issue).not.toBeNull();
      expect(issue?.code).toBe('INV-001');
      expect(issue?.field).toBe('maxCoverageDays');
      expect(issue?.message).toContain('O máximo precisa ser maior que o mínimo');
      expect(input).toEqual({ minCoverageDays: 60, maxCoverageDays: 60, leadTimeDays: 15 });
    });

    it('deve retornar INV-001 quando Dias Máximo for menor que Dias Mínimo (50/45)', () => {
      const input = Object.freeze({ minCoverageDays: 50, maxCoverageDays: 45, leadTimeDays: 15 });
      const issue = validateInventoryPolicy(input);

      expect(issue).not.toBeNull();
      expect(issue?.code).toBe('INV-001');
      expect(issue?.field).toBe('maxCoverageDays');
    });

    it('deve retornar INV-002 quando Lead Time for maior ou igual a Dias Máximo (20/40/45 e 20/40/40)', () => {
      const greater = Object.freeze({ minCoverageDays: 20, maxCoverageDays: 40, leadTimeDays: 45 });
      const equal = Object.freeze({ minCoverageDays: 20, maxCoverageDays: 40, leadTimeDays: 40 });

      const issueGreater = validateInventoryPolicy(greater);
      const issueEqual = validateInventoryPolicy(equal);

      expect(issueGreater?.code).toBe('INV-002');
      expect(issueGreater?.field).toBe('leadTimeDays');
      expect(issueEqual?.code).toBe('INV-002');
      expect(issueEqual?.field).toBe('leadTimeDays');
    });
  });

  describe('isInventoryCachePayload (CA-12)', () => {
    const validV3Payload = {
      politica: {
        historyWindowDays: 60,
        leadTimeDays: 15,
        minCoverageDays: 30,
        maxCoverageDays: 60,
      },
      kpis: {
        totalSkusAnalisados: 1,
        skusEmRupturaCritica: 0,
        skusNecessitamReposicao: 1,
        skusEstoqueSaudavel: 0,
        skusEmOverstock: 0,
        investimentoTotalSugerido: 700,
        capitalImobilizadoOverstock: 0,
        curvaADistribuicao: { qtdItens: 1, percentualItens: 100 },
      },
      produtos: [
        {
          codigo: 101,
          descricao: 'EXTRATO PROPOLIS',
          ean: '7891234567890',
          fornecedor: 'APIS FLORA',
          tipo: 'EXTRATOS',
          estoqueAtual: 50,
          vmd: 2,
          diasCobertura: 25,
          leadTime: 15,
          estoqueMinimo: 60,
          estoqueMaximo: 120,
          qtdSugeridaCompra: 70,
          custoUnitario: 10,
          precoVenda: 20,
          investimentoTotalItem: 700,
          status: 'REORDER_NEEDED',
          statusLabel: 'Abaixo do Mínimo',
          curvaAbc: 'A',
        },
      ],
      savedAt: '05/11/2026, 10:00:00',
    };

    it('deve aceitar um payload v3 válido com politica e estoqueMinimo/estoqueMaximo', () => {
      expect(isInventoryCachePayload(validV3Payload)).toBeTrue();
    });

    it('deve aceitar um payload v3 válido quando a lista de produtos estiver vazia', () => {
      expect(isInventoryCachePayload({ ...validV3Payload, produtos: [] })).toBeTrue();
    });

    it('deve rejeitar payload legado v2 (sem bloco politica ou com rop/estoqueIdeal sem estoqueMinimo)', () => {
      const legacyV2WithoutPolitica = {
        kpis: validV3Payload.kpis,
        produtos: [
          {
            codigo: 101,
            rop: 45,
            estoqueIdeal: 90,
          },
        ],
        savedAt: '04/11/2026',
      };
      const legacyItemInsideV3 = {
        ...validV3Payload,
        produtos: [{ codigo: 101, rop: 45, estoqueIdeal: 90 }],
      };

      expect(isInventoryCachePayload(legacyV2WithoutPolitica)).toBeFalse();
      expect(isInventoryCachePayload(legacyItemInsideV3)).toBeFalse();
    });

    it('deve rejeitar null, primitivos e objetos malformados', () => {
      expect(isInventoryCachePayload(null)).toBeFalse();
      expect(isInventoryCachePayload(undefined)).toBeFalse();
      expect(isInventoryCachePayload('string')).toBeFalse();
      expect(isInventoryCachePayload({})).toBeFalse();
    });
  });

  describe('extractInventoryErrorMessage (F-03)', () => {
    it('deve extrair msg quando detail é array contendo erro de domínio INV-001/INV-002', () => {
      const err = new HttpErrorResponse({
        status: 422,
        error: {
          detail: [
            {
              type: 'INV-001',
              loc: ['body', 'maxCoverageDays'],
              msg: 'Dias Máximo (maxCoverageDays = 60) deve ser maior que Dias Mínimo (minCoverageDays = 60).',
            },
          ],
        },
      });

      expect(extractInventoryErrorMessage(err)).toBe(
        'Dias Máximo (maxCoverageDays = 60) deve ser maior que Dias Mínimo (minCoverageDays = 60).'
      );
    });

    it('deve usar mensagem genérica de parâmetros inválidos quando detail é array sem código INV-', () => {
      const err = new HttpErrorResponse({
        status: 422,
        error: {
          detail: [
            {
              type: 'greater_than_equal',
              loc: ['body', 'minCoverageDays'],
              msg: 'Input should be greater than or equal to 1',
            },
          ],
        },
      });

      const msg = extractInventoryErrorMessage(err);
      expect(msg).not.toContain('Input should be');
      expect(msg.length).toBeGreaterThan(10);
    });

    it('deve retornar a própria string quando detail for texto em PT-BR (erro 500)', () => {
      const err = new HttpErrorResponse({
        status: 500,
        error: {
          detail: 'Não foi possível calcular a previsão de estoque. Tente novamente em instantes.',
        },
      });

      expect(extractInventoryErrorMessage(err)).toBe(
        'Não foi possível calcular a previsão de estoque. Tente novamente em instantes.'
      );
    });

    it('deve retornar fallback amigável quando o corpo do erro for Blob ou desconhecido', () => {
      const blobErr = new HttpErrorResponse({
        status: 500,
        error: new Blob(['erro'], { type: 'application/json' }),
      });

      const msg = extractInventoryErrorMessage(blobErr);
      expect(typeof msg).toBe('string');
      expect(msg.length).toBeGreaterThan(10);
    });
  });
});

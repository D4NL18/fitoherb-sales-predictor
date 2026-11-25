/**
 * Metadados visuais do mecanismo de preço da canibalização (F6), compartilhados com o painel "Por que?" da F7.
 */
import { CannibalizationMechanism } from '../models/cannibalization.model';

export interface MechanismVisualMeta {
  tagClass: 'tag-warning' | 'tag-info' | 'tag-positive';
  borderToken: string;
  symbol: string;
  label: string;
}

export const MECHANISM_VISUAL_META: Record<CannibalizationMechanism, MechanismVisualMeta> = {
  PRECO_MENOR_DESTROI_MARGEM: {
    tagClass: 'tag-warning',
    borderToken: 'var(--feedback-warning-bg)',
    symbol: '▲',
    label: 'Reajustar canibalizador',
  },
  PRECO_MENOR_MARGEM_PRESERVADA: {
    tagClass: 'tag-info',
    borderToken: 'var(--feedback-info-bg)',
    symbol: '▼',
    label: 'Ajustar preço da vítima',
  },
  MIGRACAO_POR_VALOR: {
    tagClass: 'tag-positive',
    borderToken: 'var(--feedback-positive-bg)',
    symbol: '↗',
    label: 'Migração por valor',
  },
};

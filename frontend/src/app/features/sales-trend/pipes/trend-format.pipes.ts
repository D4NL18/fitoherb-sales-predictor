/**
 * Pipes standalone finos para formatação consistente nos templates HTML da Tendência de Vendas.
 */
import { Pipe, PipeTransform } from '@angular/core';
import { TrendMetric, TrendWindowMeta, TrendWindowSpan } from '../models/sales-trend.model';
import { formatIsoDate } from '../utils/pt-br-format';
import {
  formatComparisonHeader,
  formatPercentChange,
  formatPointsChange,
  formatValueByMetric,
  formatWindowMonthSpan,
} from '../utils/trend-format';

@Pipe({
  name: 'trendPercent',
  standalone: true,
})
export class TrendPercentPipe implements PipeTransform {
  transform(value: number | null | undefined): string {
    return formatPercentChange(value);
  }
}

@Pipe({
  name: 'trendPoints',
  standalone: true,
})
export class TrendPointsPipe implements PipeTransform {
  transform(value: number | null | undefined): string {
    return formatPointsChange(value);
  }
}

@Pipe({
  name: 'trendValue',
  standalone: true,
})
export class TrendValuePipe implements PipeTransform {
  transform(value: number | null | undefined, metric: TrendMetric = 'revenue', decimals?: number): string {
    return formatValueByMetric(value, metric, decimals);
  }
}

@Pipe({
  name: 'trendSpan',
  standalone: true,
})
export class TrendMonthSpanPipe implements PipeTransform {
  transform(span: TrendWindowSpan): string {
    return formatWindowMonthSpan(span);
  }
}

@Pipe({
  name: 'trendHeader',
  standalone: true,
})
export class TrendComparisonHeaderPipe implements PipeTransform {
  transform(windowMeta: TrendWindowMeta): string {
    return formatComparisonHeader(windowMeta);
  }
}

@Pipe({
  name: 'ptBrDate',
  standalone: true,
})
export class PtBrDatePipe implements PipeTransform {
  transform(isoDate: string | null | undefined): string {
    return formatIsoDate(isoDate);
  }
}

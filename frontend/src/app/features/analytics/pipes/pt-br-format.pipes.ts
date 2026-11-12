/**
 * Pipes puros de formatação pt-BR do módulo Analytics (Design Plan §4: formatação só por pipes no template).
 * Delegam para `utils/pt-br-format.ts`, que segue o arredondamento meio para cima de P-065.
 */
import { Pipe, PipeTransform } from '@angular/core';
import { formatCurrency, formatDecimal, formatIsoDate, formatPercent, formatPosition } from '../utils/pt-br-format';

@Pipe({ name: 'ptDecimal', standalone: true })
export class PtDecimalPipe implements PipeTransform {
  transform(value: number, fractionDigits = 0): string {
    return formatDecimal(value, fractionDigits);
  }
}

@Pipe({ name: 'ptPercent', standalone: true })
export class PtPercentPipe implements PipeTransform {
  transform(ratio: number, fractionDigits = 0): string {
    return formatPercent(ratio, fractionDigits);
  }
}

@Pipe({ name: 'brl', standalone: true })
export class BrlPipe implements PipeTransform {
  transform(value: number): string {
    return formatCurrency(value);
  }
}

@Pipe({ name: 'ptDate', standalone: true })
export class PtDatePipe implements PipeTransform {
  transform(isoDate: string): string {
    return formatIsoDate(isoDate);
  }
}

@Pipe({ name: 'listPosition', standalone: true })
export class ListPositionPipe implements PipeTransform {
  transform(position: number): string {
    return formatPosition(position);
  }
}

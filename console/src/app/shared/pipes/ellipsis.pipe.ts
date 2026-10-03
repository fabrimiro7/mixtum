import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'ellipsis', standalone: true })
export class EllipsisPipe implements PipeTransform {
  // Truncate string to `max` chars and append `suffix` (default: " [...]")
  transform(value: unknown, max = 30, suffix = ' [...]'): string {
    const str = (value ?? '').toString().trim();
    if (!str) return '';
    if (str.length <= max) return str;
    return str.slice(0, max).trimEnd() + suffix;
  }
}
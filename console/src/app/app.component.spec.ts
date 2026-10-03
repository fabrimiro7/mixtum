import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { AppComponent } from './app.component';
import { AuthService, BrandingSummary } from './core/services/auth.service';

describe('AppComponent branding', () => {
  it('applies the API theme and removes it when branding is cleared', () => {
    const branding = new BehaviorSubject<BrandingSummary | null>(null);
    TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: { branding$: branding.asObservable() } }],
    });
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const root = fixture.nativeElement.querySelector('div') as HTMLDivElement;
    expect(root.style.getPropertyValue('--mixtum-primary')).toBe('');

    branding.next({ logo_compact: null, colors: {}, theme: { primary: '#123456', on_primary: '#FFFFFF' } });
    fixture.detectChanges();
    expect(root.style.getPropertyValue('--mixtum-primary')).toBe('#123456');
    expect(root.style.getPropertyValue('--mixtum-on-primary')).toBe('#FFFFFF');

    branding.next(null);
    fixture.detectChanges();
    expect(root.style.getPropertyValue('--mixtum-primary')).toBe('');
    expect(root.style.getPropertyValue('--mixtum-on-primary')).toBe('');
  });
});

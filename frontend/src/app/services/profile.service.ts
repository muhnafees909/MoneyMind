import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface AdvisorProfile {
  employment_status: 'employed' | 'self_employed' | 'student' | 'unemployed' | null;
  annual_income: number | null;
  marital_status: 'single' | 'married' | null;
  dependents: number | null;
  housing_status: 'rent' | 'own' | 'family' | null;
  birth_year: number | null;
  updated_at: string | null;
}

/**
 * Advisor-personalization profile. Sensitive context: this service is
 * deliberately stateless — no caching, no logging. Data lives only in the
 * profile screen's component while it's open, and on the server.
 */
@Injectable({
  providedIn: 'root'
})
export class ProfileService {
  private apiUrl = `${environment.apiUrl}/api/profile`;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      Authorization: `Bearer ${this.authService.getToken()}`
    });
  }

  getProfile(): Observable<AdvisorProfile> {
    return this.http.get<AdvisorProfile>(this.apiUrl, { headers: this.getHeaders() });
  }

  updateProfile(profile: Partial<AdvisorProfile>): Observable<AdvisorProfile> {
    return this.http.put<AdvisorProfile>(this.apiUrl, profile, { headers: this.getHeaders() });
  }
}

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

// Plaid Link is loaded globally via the script tag in index.html.
declare var Plaid: any;

/** One bank connection that Plaid says needs the user to act on. Mirrors the
 *  backend's item payload from a 409 ITEM_ACTION_REQUIRED response. */
export interface ReauthItem {
  item_id: string;
  institution_name: string | null;
  error_code: string;
  message: string;
  reconnect: boolean; // true → Plaid Link update mode can fix it
}

/**
 * Shared launcher for Plaid Link. Handles the update-mode reconnect flow used
 * by Accounts and Envelopes when a linked bank reports ITEM_LOGIN_REQUIRED.
 */
@Injectable({ providedIn: 'root' })
export class PlaidLinkService {
  private plaidUrl = `${environment.apiUrl}/api/plaid`;

  constructor(private http: HttpClient) {}

  /** Create an UPDATE-MODE link token for an existing item (re-auth). */
  createUpdateLinkToken(itemId: string): Observable<{ link_token: string }> {
    return this.http.post<{ link_token: string }>(
      `${this.plaidUrl}/create-update-link-token`,
      { item_id: itemId }
    );
  }

  /**
   * Open Plaid Link with a given token. In update mode there's no public token
   * to exchange — the existing access token becomes valid again — so `onSuccess`
   * just signals the caller to retry its sync. `onExit` fires if the user
   * dismisses Link without finishing.
   */
  open(linkToken: string, onSuccess: () => void, onExit?: () => void): void {
    if (typeof Plaid === 'undefined') {
      console.error('Plaid Link script not loaded');
      onExit?.();
      return;
    }
    const handler = Plaid.create({
      token: linkToken,
      onSuccess: () => onSuccess(),
      onExit: (err: any) => {
        if (err) {
          console.error('Plaid Link (update mode) exit error:', err);
        }
        onExit?.();
      }
    });
    handler.open();
  }
}

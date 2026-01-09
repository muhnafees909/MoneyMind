import { Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmationModalComponent } from '../components/modals/confirmation-modal/confirmation-modal';
import { AlertModalComponent } from '../components/modals/alert-modal/alert-modal';
import { firstValueFrom } from 'rxjs';

export type AlertType = 'error' | 'success' | 'info';

export interface AlertData {
  type: AlertType;
  title?: string;
  message: string;
}

export interface ConfirmData {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ModalService {
  constructor(private dialog: MatDialog) {}

  /**
   * Show error modal
   */
  showError(message: string, title: string = 'Error'): void {
    this.dialog.open(AlertModalComponent, {
      data: { type: 'error', title, message },
      width: '400px',
      panelClass: 'custom-modal'
    });
  }

  /**
   * Show success modal
   */
  showSuccess(message: string, title: string = 'Success'): void {
    this.dialog.open(AlertModalComponent, {
      data: { type: 'success', title, message },
      width: '400px',
      panelClass: 'custom-modal'
    });
  }

  /**
   * Show info modal
   */
  showInfo(message: string, title: string = 'Information'): void {
    this.dialog.open(AlertModalComponent, {
      data: { type: 'info', title, message },
      width: '400px',
      panelClass: 'custom-modal'
    });
  }

  /**
   * Show confirmation modal
   * Returns a promise that resolves to true if confirmed, false if cancelled
   */
  async showConfirm(
    message: string,
    title: string = 'Confirm Action',
    confirmText: string = 'Confirm',
    cancelText: string = 'Cancel'
  ): Promise<boolean> {
    const dialogRef = this.dialog.open(ConfirmationModalComponent, {
      data: { title, message, confirmText, cancelText },
      width: '400px',
      panelClass: 'custom-modal'
    });

    const result = await firstValueFrom(dialogRef.afterClosed());
    return result === true;
  }
}

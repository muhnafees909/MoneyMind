import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import {
  LucideCircleCheck,
  LucideInfo,
  LucideOctagonAlert,
  LucideX
} from '@lucide/angular';
import { AlertData } from '../../../services/modal.service';

@Component({
  selector: 'app-alert-modal',
  standalone: true,
  imports: [CommonModule, MatDialogModule, LucideCircleCheck, LucideInfo, LucideOctagonAlert, LucideX],
  templateUrl: './alert-modal.html',
  styleUrl: './alert-modal.scss'
})
export class AlertModalComponent {
  constructor(
    public dialogRef: MatDialogRef<AlertModalComponent>,
    @Inject(MAT_DIALOG_DATA) public data: AlertData
  ) {}

  close(): void {
    this.dialogRef.close();
  }
}

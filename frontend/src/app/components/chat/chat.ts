import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ChatService, ChatMessage, ChatResponse } from '../../services/chat.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule
  ],
  templateUrl: './chat.html',
  styleUrl: './chat.scss'
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages: ChatMessage[] = [];
  userInput: string = '';
  loading: boolean = false;
  error: string | null = null;
  shouldScroll: boolean = false;

  constructor(private chatService: ChatService) {}

  ngOnInit(): void {
    // Add initial welcome message
    this.messages.push({
      role: 'assistant',
      content: 'Hello! I\'m your personal financial advisor. I can help you with questions about your budgets, spending, goals, and financial decisions. Feel free to ask me anything finance-related!',
      timestamp: new Date()
    });
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  sendMessage(): void {
    // Validate input
    if (!this.userInput.trim()) {
      return;
    }

    // Add user message to chat
    const userMessage: ChatMessage = {
      role: 'user',
      content: this.userInput,
      timestamp: new Date()
    };
    this.messages.push(userMessage);

    // Clear input and set loading state
    const messageToSend = this.userInput;
    this.userInput = '';
    this.loading = true;
    this.error = null;
    this.shouldScroll = true;

    // Send message to backend
    this.chatService.sendMessage(messageToSend).subscribe({
      next: (response: ChatResponse) => {
        // Add AI response to chat
        const aiMessage: ChatMessage = {
          role: 'assistant',
          content: response.response,
          timestamp: new Date()
        };
        this.messages.push(aiMessage);
        this.loading = false;
        this.shouldScroll = true;
      },
      error: (error) => {
        this.loading = false;

        // Handle different error types
        if (error.status === 401) {
          this.error = 'Session expired. Please log in again.';
        } else if (error.status === 400) {
          this.error = error.error?.error || 'Invalid request. Please try again.';
        } else if (error.status === 429) {
          this.error = 'Too many requests. Please wait a moment and try again.';
        } else if (error.status === 503) {
          this.error = 'AI service is temporarily unavailable. Please try again later.';
        } else if (error.status === 504) {
          this.error = 'Request timed out. Please try again.';
        } else {
          this.error = error.error?.error || 'An error occurred while getting a response. Please try again.';
        }

        this.shouldScroll = true;
      }
    });
  }

  private scrollToBottom(): void {
    try {
      this.messagesContainer.nativeElement.scrollTop = this.messagesContainer.nativeElement.scrollHeight;
    } catch (err) {
      console.error('Error scrolling to bottom:', err);
    }
  }

  clearChat(): void {
    // Reset to welcome message
    this.messages = [{
      role: 'assistant',
      content: 'Hello! I\'m your personal financial advisor. I can help you with questions about your budgets, spending, goals, and financial decisions. Feel free to ask me anything finance-related!',
      timestamp: new Date()
    }];
    this.error = null;
    this.userInput = '';
  }

  get hasError(): boolean {
    return !!this.error;
  }

  get isInputDisabled(): boolean {
    return this.loading || !this.userInput.trim();
  }
}

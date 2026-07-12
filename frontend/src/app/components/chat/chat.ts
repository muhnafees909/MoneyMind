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
import { MarkdownModule } from 'ngx-markdown';
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
    MatTooltipModule,
    MarkdownModule
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
    if (!this.userInput.trim()) {
      return;
    }

    // Prior turns (before this message) so the advisor can follow up on its
    // own clarifying questions. Skip the canned greeting; cap at 10 turns.
    const history = this.messages
      .filter((m, i) => !(i === 0 && m.role === 'assistant'))
      .slice(-10);

    const userMessage: ChatMessage = {
      role: 'user',
      content: this.userInput,
      timestamp: new Date()
    };
    this.messages.push(userMessage);

    const messageToSend = this.userInput;
    this.userInput = '';
    this.loading = true;
    this.error = null;
    this.shouldScroll = true;

    this.chatService.sendMessage(messageToSend, history).subscribe({
      next: (response: ChatResponse) => {
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

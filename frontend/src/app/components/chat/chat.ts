import {
  AfterViewChecked,
  Component,
  ElementRef,
  NgZone,
  OnInit,
  ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { animate, stagger } from 'motion';
import { MarkdownModule } from 'ngx-markdown';
import {
  LucideChartPie,
  LucideCornerDownLeft,
  LucideEraser,
  LucideOctagonAlert,
  LucidePiggyBank,
  LucideReceiptText,
  LucideTarget,
  LucideTrendingDown,
  LucideTriangleAlert,
  LucideWallet
} from '@lucide/angular';
import {
  AdvisorUsage,
  ChatService,
  ChatMessage,
  ChatResponse
} from '../../services/chat.service';

interface AdvisorMessage extends ChatMessage {
  context?: ChatResponse['context_used'];
}

interface StarterPrompt {
  icon: 'chart' | 'target' | 'trim' | 'save';
  label: string;
  question: string;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MarkdownModule,
    LucideChartPie,
    LucideCornerDownLeft,
    LucideEraser,
    LucideOctagonAlert,
    LucidePiggyBank,
    LucideReceiptText,
    LucideTarget,
    LucideTrendingDown,
    LucideTriangleAlert,
    LucideWallet
  ],
  templateUrl: './chat.html',
  styleUrl: './chat.scss'
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages: AdvisorMessage[] = [];
  userInput = '';
  loading = false;
  error: string | null = null;
  shouldScroll = false;
  preAnim = true;
  usage: AdvisorUsage | null = null;

  readonly starterPrompts: StarterPrompt[] = [
    {
      icon: 'chart',
      label: 'Where did this month go?',
      question: 'Break down my spending this month — where did most of it go?'
    },
    {
      icon: 'target',
      label: 'Am I on track for my goals?',
      question: 'Am I on track to hit my savings goals? What would speed them up?'
    },
    {
      icon: 'trim',
      label: 'What should I cut back on?',
      question: 'Looking at my budgets, which categories should I cut back on?'
    },
    {
      icon: 'save',
      label: 'How much can I save monthly?',
      question: 'Based on my income and spending, how much could I realistically save each month?'
    }
  ];

  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(
    private chatService: ChatService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit(): void {
    setTimeout(() => this.runEntrance(), 40);
    // Seed the usage indicator; every send refreshes it from the response
    this.chatService.getUsage().subscribe({
      next: (usage) => (this.usage = usage),
      error: () => {} // indicator is a courtesy — the server enforces regardless
    });
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  get isEmpty(): boolean {
    return this.messages.length === 0;
  }

  askStarter(prompt: StarterPrompt): void {
    this.userInput = prompt.question;
    this.sendMessage();
  }

  get dailyExhausted(): boolean {
    return !!this.usage && this.usage.daily.remaining === 0;
  }

  get usageWarn(): boolean {
    return !!this.usage && this.usage.daily.remaining > 0 && this.usage.daily.remaining <= 5;
  }

  get dailyResetLabel(): string {
    const seconds = this.usage?.daily.resets_in_seconds ?? 0;
    if (seconds < 60) {
      return 'under a minute';
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours && minutes) {
      return `${hours}h ${minutes}m`;
    }
    return hours ? `${hours}h` : `${minutes}m`;
  }

  sendMessage(): void {
    if (!this.userInput.trim() || this.loading || this.dailyExhausted) {
      return;
    }

    // Prior turns so the advisor can follow up on its own clarifying
    // questions; cap at 10 turns.
    const history = this.messages.slice(-10);

    this.messages.push({
      role: 'user',
      content: this.userInput,
      timestamp: new Date()
    });

    const messageToSend = this.userInput;
    this.userInput = '';
    this.loading = true;
    this.error = null;
    this.shouldScroll = true;

    this.chatService.sendMessage(messageToSend, history).subscribe({
      next: (response: ChatResponse) => {
        this.messages.push({
          role: 'assistant',
          content: this.markNumbers(response.response),
          timestamp: new Date(),
          context: response.context_used
        });
        if (response.usage) {
          this.usage = response.usage;
        }
        this.loading = false;
        this.shouldScroll = true;
      },
      error: (error) => {
        this.loading = false;
        const body = error.error ?? {};
        const code: string | undefined = body.error_code;
        if (error.status === 401) {
          this.error = 'Session expired. Please log in again.';
        } else if (error.status === 400) {
          this.error = body.error || 'Invalid request. Please try again.';
        } else if (error.status === 429 && code?.startsWith('ADVISOR_')) {
          // MoneyMind's own limit — the server's message says when to retry
          this.error = body.error;
          if (body.usage) {
            this.usage = body.usage;
          }
        } else if (error.status === 429) {
          // OpenAI throttling us — different failure, different message
          this.error =
            body.error ||
            'The advisor is handling a lot of requests right now. Try again in a minute.';
        } else if (error.status === 503) {
          this.error = body.error || 'The advisor is temporarily unavailable. Try again shortly.';
        } else if (error.status === 504) {
          this.error = body.error || 'That one took too long. Try asking again.';
        } else {
          this.error = body.error || 'Something went wrong getting a response. Try again.';
        }
        this.shouldScroll = true;
      }
    });
  }

  /**
   * Wrap cited figures ($1,234.56 / 12% / 4.5x) in backticks so markdown
   * renders them as `code`, which the stylesheet sets as mono data chips —
   * the advisor's numbers wear the same tabular treatment as the app.
   */
  private markNumbers(content: string): string {
    if (content.includes('```')) {
      return content; // don't touch responses that carry real code blocks
    }
    return content.replace(
      /(?<![`\w])(\$\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d+)?%)(?!`)/g,
      '`$1`'
    );
  }

  clearChat(): void {
    this.messages = [];
    this.error = null;
    this.userInput = '';
  }

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  private scrollToBottom(): void {
    try {
      this.messagesContainer.nativeElement.scrollTop =
        this.messagesContainer.nativeElement.scrollHeight;
    } catch {
      // container not rendered yet (empty state) — nothing to scroll
    }
  }

  private runEntrance(): void {
    if (this.reducedMotion) {
      this.preAnim = false;
      return;
    }
    const els = this.host.nativeElement.querySelectorAll('[data-animate]');
    this.preAnim = false;
    if (els.length === 0) {
      return;
    }
    this.zone.runOutsideAngular(() => {
      animate(
        els,
        { opacity: [0, 1], transform: ['translateY(10px)', 'translateY(0px)'] },
        { duration: 0.5, delay: stagger(0.06), ease: [0.22, 1, 0.36, 1] }
      );
    });
  }
}

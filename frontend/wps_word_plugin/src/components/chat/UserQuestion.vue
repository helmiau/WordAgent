<template>
  <form class="user-question" :class="{ answered: readonly }" @submit.prevent="submit">
    <div class="question-heading">
      {{ $t('chat.clarificationTitle') }}
    </div>
    <p class="question-hint">
      {{ $t('chat.clarificationHint') }}
    </p>
    <fieldset v-for="question in request.questions" :key="question.id" :disabled="disabled || readonly">
      <legend>{{ question.question }}</legend>
      <label
        v-for="option in question.options.slice(0, 4)"
        :key="option"
        class="question-option"
        :class="{ selected: choices[question.id] === option }"
      >
        <input
          v-model="choices[question.id]"
          type="radio"
          :name="question.id"
          :value="option"
        />
        <span>{{ option }}</span>
      </label>
      <label class="question-option" :class="{ selected: choices[question.id] === null }">
        <input
          v-model="choices[question.id]"
          type="radio"
          :name="question.id"
          :value="null"
        />
        <span>{{ $t('chat.clarificationCustom') }}</span>
      </label>
      <textarea
        v-model="customAnswers[question.id]"
        class="question-custom"
        rows="2"
        maxlength="4000"
        :aria-label="$t('chat.clarificationCustom')"
        :placeholder="$t('chat.clarificationPlaceholder')"
        @focus="choices[question.id] = null"
        @input="choices[question.id] = null"
      ></textarea>
    </fieldset>
    <button
      v-if="!readonly"
      class="question-submit"
      type="submit"
      :disabled="disabled || !canSubmit"
    >
      {{ $t(disabled ? 'chat.clarificationSubmitting' : 'chat.clarificationContinue') }}
    </button>
  </form>
</template>

<script>
export default {
  name: 'UserQuestion',
  props: {
    request: { type: Object, required: true },
    response: { type: Object, default: null },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false }
  },
  emits: ['answer'],
  data: () => ({ choices: {}, customAnswers: {} }),
  computed: {
    answers() {
      return this.request.questions.map(question => ({
        id: question.id,
        answer: (this.choices[question.id] === null
          ? this.customAnswers[question.id] || '' : this.choices[question.id] || '').trim()
      }));
    },
    canSubmit() {
      return this.answers.length > 0 && this.answers.every(item => item.answer.length > 0 && item.answer.length <= 4000);
    }
  },
  watch: {
    response: {
      immediate: true,
      handler(response) {
        if (!response) {
          return;
        }
        for (const question of this.request.questions) {
          const answer = response.answers.find(item => item.id === question.id)?.answer;
          if (answer === undefined) {
            continue;
          }
          // Preserve the explicit custom choice on the live card.
          if (this.choices[question.id] === null && (this.customAnswers[question.id] || '').trim() === answer) {
            continue;
          }
          const isOption = question.options.slice(0, 4).includes(answer);
          this.choices[question.id] = isOption ? answer : null;
          this.customAnswers[question.id] = isOption ? '' : answer;
        }
      }
    }
  },
  methods: {
    submit() {
      if (!this.disabled && !this.readonly && this.canSubmit) {
        this.$emit('answer', { answers: this.answers });
      }
    }
  }
};
</script>

<style scoped>
.user-question { box-sizing: border-box; padding: 14px; margin: 10px 0 8px; border: 1px solid #dcdffa; border-radius: 10px; background: #f8f9ff; color: #303648; }
.question-heading { font-size: 13px; font-weight: 600; color: #5969d8; }
.question-hint { margin: 5px 0 12px; font-size: 12px; color: #7b8192; }
fieldset { min-width: 0; padding: 0; margin: 0 0 12px; border: 0; }
legend { width: 100%; padding: 0; margin-bottom: 8px; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.question-option { display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; margin: 5px 0; border: 1px solid #e3e5ed; border-radius: 6px; background: #fff; font-size: 12px; cursor: pointer; overflow-wrap: anywhere; }
.question-option.selected { border-color: #6c7aeb; background: #f0f2ff; }
.question-option input { margin: 2px 0 0; accent-color: #6878eb; flex-shrink: 0; }
.user-question.answered .question-option { cursor: default; }
.user-question.answered .question-option.selected { border-color: #b5b8c0; background: #f0f1f3; }
.user-question.answered input[type="radio"] { appearance: none; width: 13px; height: 13px; border: 1px solid #a4a8b0; border-radius: 50%; background: #fff; opacity: 1; }
.user-question.answered input[type="radio"]:checked { background: #8b909a; box-shadow: inset 0 0 0 3px #fff; }
.user-question.answered .question-custom { opacity: 1; -webkit-text-fill-color: #303648; }
.question-custom { display: block; box-sizing: border-box; width: 100%; min-height: 54px; resize: vertical; padding: 8px 10px; border: 1px solid #e3e5ed; border-radius: 6px; background: #fff; font: inherit; font-size: 12px; color: inherit; }
.question-custom:focus { outline: 2px solid #9aa5f5; outline-offset: 1px; }
.question-submit { display: block; margin-left: auto; border: 0; border-radius: 6px; padding: 8px 14px; background: #6878eb; color: white; font-size: 12px; cursor: pointer; }
.question-submit:disabled { opacity: .5; cursor: not-allowed; }
</style>

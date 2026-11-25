import type { TranslationOverrides } from './define-locale'

export const arCommon = {
  sharedMetrics: {
    consentTitle: 'جمع إحصاءات الاستخدام محليًا؟',
    dialogTitle: 'إحصاءات الاستخدام',
    consentBody:
      'يمكن لـ Nara إحصاء طريقة استخدامك له: طول الجلسات، والنماذج والأدوات التي تعمل، ومتى يفشل شيء ما. لا يسجّل أبدًا رسائلك أو ملفاتك أو مساراتك أو نصوص الأخطاء.',
    whatIsCollected: 'ما الذي يُحصى',
    collectedActivity: 'الجلسات: الطول، والنتيجة، ونوع الخطأ، ووقت النشاط في اليوم',
    collectedModels: 'النماذج: أيّها يُستخدم، وإجمالي الرموز',
    collectedNames: 'الميزات: الأدوات المدمجة والأوامر وأقسام التطبيق والإعدادات المستخدمة أو المعطّلة',
    collectedMilestones: 'الإعداد: الخطوات المكتملة، واتصالات المزوّدين، وعدد المهارات والإضافات والمهام',
    collectedReliability: 'سلامة التطبيق: الأعطال، وسرعة البدء والرد، والتحديثات، واتصالات المراسلة',
    collectedUsage: 'جودة الوكيل: التعديلات الفاشلة، واستدعاءات الأدوات المعطوبة، والحلقات العالقة، والتكلفة لكل مهمة',
    collectedMachine: 'الجهاز: نظام التشغيل، ونطاق الذاكرة، ونوع وحدة الرسوميات، وإصدار Nara، واستخدام نموذج محلي',
    sending:
      'يحفظ هذا الخيار العدادات على هذا الجهاز فقط ولا يرسل شيئًا. يتطلب الإرسال عنوان وجهة وإعدادًا منفصلين في config.yaml. يمكنك تغيير الجمع المحلي من الإعدادات.',
    readDocs: 'اقرأ التفاصيل الكاملة',
    share: 'الجمع محليًا',
    off: 'لا، شكرًا',
    saveFailed: 'تعذّر حفظ اختيارك',
    sendLabel: 'جمع إحصاءات الاستخدام على هذا الجهاز',
    sendDesc:
      'يحفظ العدادات محليًا ولا يرسل شيئًا. لا يسجل رسائلك أو ملفاتك أو مساراتك أو نصوص الأخطاء.',
    unavailable: 'حدّث واجهة Nara الخلفية لتغيير هذا الإعداد.',
    stripBody: 'إحصاءات فقط. لا تشمل أبدًا رسائلك أو ملفاتك.',
    stripReaskBody: 'نسألك مرة أخرى: ربما حفظ إصدار سابق «لا، شكرًا» قبل أن ترى هذا السؤال.',
    stripChoices: { share: 'الجمع محليًا', off: 'لا، شكرًا' },
    stripDetails: 'التفاصيل'
  },
  common: {
    apply: 'تطبيق',
    back: 'رجوع',
    save: 'حفظ',
    saving: 'جار الحفظ...',
    cancel: 'إلغاء',
    change: 'تغيير',
    choose: 'اختيار',
    clear: 'مسح',
    close: 'إغلاق',
    collapse: 'طي',
    confirm: 'تأكيد',
    connect: 'اتصال',
    connecting: 'جار الاتصال',
    continue: 'متابعة',
    bots: 'الروبوتات',
    copied: 'تم النسخ',
    copy: 'نسخ',
    copyFailed: 'فشل النسخ',
    delete: 'حذف',
    docs: 'الوثائق',
    done: 'تم',
    error: 'خطأ',
    failed: 'فشل',
    free: 'مجاني',
    loading: 'جار التحميل...',
    notSet: 'غير مضبوط',
    refresh: 'تحديث',
    remove: 'إزالة',
    replace: 'استبدال',
    retry: 'إعادة المحاولة',
    run: 'تشغيل',
    send: 'إرسال',
    set: 'ضبط',
    skip: 'تخطي',
    update: 'تحديث',
    on: 'مفعل',
    off: 'معطل'
  },
  ui: {
    search: {
      clear: 'مسح البحث'
    },
    logs: {
      bottom: 'أسفل السجل',
      search: 'البحث في السجلات…',
      top: 'أعلى السجل'
    },
    pagination: {
      label: 'ترقيم الصفحات',
      previous: 'السابق',
      previousAria: 'الصفحة السابقة',
      next: 'التالي',
      nextAria: 'الصفحة التالية'
    },
    sidebar: {
      title: 'الشريط الجانبي',
      description: 'تنقل التطبيق',
      toggle: open => `${open ? 'إظهار' : 'إخفاء'} الشريط الجانبي`
    }
  }
} satisfies Pick<TranslationOverrides, 'sharedMetrics' | 'common' | 'ui'>

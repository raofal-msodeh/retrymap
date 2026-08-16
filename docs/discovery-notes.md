# RetryMap — Discovery Notes

## المشكلة والأدلة

إعادة المحاولة من أصعب أجزاء هندسة الموثوقية: أغلب التنفيذات المنزلية تكرر أنماطًا خاطئة — backoff خطي بلا سقف يجعل الفشل الطويل يستنزف النظام، غياب jitter يجعل آلاف العملاء يعيدون المحاولة في نفس اللحظة (thundering herd)، وعدم توثيق "لماذا اخترنا هذه السياسة" يجعلها تتآكل عبر مراجعات الكود. الأدلة:

- [AWS Architecture Blog — Exponential Backoff And Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/): jitter يقلل التحميل الكلي بشكل كبير حتى مع نفس إجمالي وقت الانتظار؛ full jitter هو الخيار الافتراضي الآمن.
- [Google SRE — Retry Budgets](https://sre.google/workbook/retry-budgets/): إعادة المحاولة يجب أن تُحسب كتكلفة خدمة ويجب أن يكون لها حدود زمنية (deadline).
- tenacity وbackoff وpybackoff على PyPI: مكتبات ناضجة لكنها ثقيلة، APIها يعتمد على decorators فقط (صعب الاختبار الحتمي بسبب النوم)، ولا تملك مفهوم "تجربة موثقة" (experiment) يمكن تدقيقه.
- [HN: retry storms](https://news.ycombinator.com/item?id=31108297): حوادث production ناتجة عن retry storms موثقة مرارًا.

## البدائل والفجوة

| الأداة | النهج | الاختبار الحتمي | توثيق التجارب | الحجم |
| --- | --- | --- | --- | --- |
| tenacity | decorators + wait objects | جزئي (mock sleep) | لا | كبير، API واسع |
| backoff | decorators فقط | جزئي | لا | متوسط |
| pybackoff | decorator بسيط | لا | لا | صغير |
| retrymap (هنا) | دالة `retry_call` قابلة للحقن + `compute_wait` حتمية + `Experiment` | نعم (sleep قابل للحقن + RNG seedable) | نعم (Experiment dataclass) | صغير، صفر تبعيات |

الفجوة: لا توجد مكتبة Python خفيفة تجعل جدول الانتظار **قابلاً للحساب الحتمي** (بلا نوم داخلي)، وتقبل **predicate** لقرارات إعادة المحاولة، وتملك **_experiment_** ككيان من الدرجة الأولى لتدقيق قرارات السياسة.

## القرار

مكتبة Python 3.11+، صفر تبعيات، API على شكل `retry_call(fn, config)` مع `sleep` و`rng` قابلين للحقن للاختبارات الحتمية. سياسة Union (Exponential | Constant | Linear | NoRetry)، `retry_on`/`do_not_retry` نوعًا أو predicate، `total_deadline` يرفع `WaitExceededError`، و`MaxAttemptsError` يحمل قائمة الاستثناءات الكاملة.

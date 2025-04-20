document.addEventListener('DOMContentLoaded', function() {
    // Обновление текущего времени
    function updateCurrentTime() {
        const now = new Date();
        const options = { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            hour12: false 
        };
        const timeString = now.toLocaleTimeString('ru-RU', options);
        
        const timeElements = document.querySelectorAll('.current-time');
        timeElements.forEach(el => {
            el.textContent = timeString;
        });
    }
    
    // Инициализация подсказок
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0) {
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
    
    // Инициализация всплывающих окон
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    if (popoverTriggerList.length > 0) {
        const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    }
    
    // Обновление времени каждую секунду
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Подтверждение удаления
    const deleteButtons = document.querySelectorAll('.confirm-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите удалить этот элемент?')) {
                e.preventDefault();
            }
        });
    });
    
    // Копирование текста в буфер обмена
    const copyButtons = document.querySelectorAll('.copy-text');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy-text');
            navigator.clipboard.writeText(textToCopy).then(() => {
                // Показать уведомление об успешном копировании
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i> Скопировано';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Ошибка при копировании текста: ', err);
            });
        });
    });
    
    // Отображение/скрытие опций планирования поста
    const scheduleCheckbox = document.getElementById('schedule_post');
    const scheduleOptions = document.getElementById('scheduleOptions');
    
    if (scheduleCheckbox && scheduleOptions) {
        scheduleCheckbox.addEventListener('change', function() {
            if (this.checked) {
                scheduleOptions.style.display = 'block';
                // Анимация появления
                scheduleOptions.style.opacity = 0;
                setTimeout(() => {
                    scheduleOptions.style.transition = 'opacity 0.3s ease';
                    scheduleOptions.style.opacity = 1;
                }, 10);
            } else {
                // Анимация исчезновения
                scheduleOptions.style.transition = 'opacity 0.3s ease';
                scheduleOptions.style.opacity = 0;
                setTimeout(() => {
                    scheduleOptions.style.display = 'none';
                }, 300);
            }
        });
    }
    
    // Предпросмотр поста
    const previewButton = document.getElementById('previewPostBtn');
    const themeInput = document.getElementById('theme');
    const previewText = document.getElementById('previewText');
    const previewImage = document.getElementById('previewImage');
    
    if (previewButton && themeInput && previewText) {
        previewButton.addEventListener('click', function() {
            const theme = themeInput.value.trim();
            
            if (theme) {
                // Пример эмоционального контента на основе темы
                const emotions = document.querySelector('input[name="post_emotion"]:checked').value;
                let emoji = '📊'; // По умолчанию
                let text = '';
                
                switch(emotions) {
                    case 'motivational':
                        emoji = '🔥';
                        text = `${emoji} <strong>Стань лучшим трейдером!</strong>\n\n${theme}\n\nПомните, что успех в трейдинге — это не о везении, а о дисциплине и постоянном развитии! 💪 Действуйте по плану и результаты не заставят себя ждать!`;
                        break;
                    case 'educational':
                        emoji = '📚';
                        text = `${emoji} <strong>Обучающий совет дня:</strong>\n\n${theme}\n\nРазвивайте свои навыки трейдинга каждый день, и вы увидите, как растет ваш портфель вместе с вашими знаниями.`;
                        break;
                    case 'analytical':
                        emoji = '📈';
                        text = `${emoji} <strong>Аналитический обзор:</strong>\n\n${theme}\n\nДанные и факты — ваше главное оружие в принятии торговых решений. Анализируйте, исследуйте, действуйте на основе данных.`;
                        break;
                    case 'cautionary':
                        emoji = '⚠️';
                        text = `${emoji} <strong>Внимание! Важное предупреждение:</strong>\n\n${theme}\n\nПомните о рисках и всегда защищайте свой капитал. Разумное управление рисками — основа долгосрочного успеха.`;
                        break;
                }
                
                previewText.innerHTML = `<p>${text.replace(/\n/g, '<br>')}</p>`;
                
                // Добавление примера изображения
                previewImage.innerHTML = `<img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&auto=format&fit=crop&q=80" class="img-fluid w-100 h-100 object-fit-cover" alt="Финансовое изображение">`;
            } else {
                previewText.innerHTML = `<div class="placeholder-text text-center text-muted p-4">Введите тему поста для предпросмотра</div>`;
                previewImage.innerHTML = `<i class="fas fa-image fa-3x text-muted"></i>`;
            }
        });
    }
    
    // Анимации для карточек при их появлении на странице
    function animateElements() {
        const cards = document.querySelectorAll('.card');
        
        cards.forEach((card, index) => {
            setTimeout(() => {
                card.classList.add('card-animated');
            }, 100 * index);
        });
    }
    
    // Выполнить анимацию после загрузки страницы
    animateElements();
});